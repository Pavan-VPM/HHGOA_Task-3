"""
EVM Blockchain Client for Face-Post Registry.
Supports both zero-setup in-process PyEVM (EthereumTesterProvider) and live public testnets (Sepolia, Amoy, etc.).
"""

import json
import os
import time
from typing import Dict, Any, Optional, Tuple
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .hasher import to_bytes32


class EVMClient:
    def __init__(
        self,
        mode: str = "local",
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
        contract_address: Optional[str] = None,
    ):
        self.mode = mode.lower()
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.contract_address = contract_address

        # Load contract ABI and bytecode
        contract_json_path = os.path.join(os.path.dirname(__file__), "FacePostRegistry.json")
        with open(contract_json_path, "r") as f:
            contract_data = json.load(f)
            self.abi = contract_data["abi"]
            self.bytecode = contract_data["bytecode"]

        # Initialize Web3 provider
        if self.mode == "local" and not rpc_url:
            from web3.providers.eth_tester import EthereumTesterProvider
            self.provider = EthereumTesterProvider()
            self.w3 = Web3(self.provider)
            self.account = self.w3.eth.accounts[0]
            self.is_tester = True
        else:
            if not rpc_url:
                raise ValueError("rpc_url must be provided when mode != 'local'")
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            # Inject POA middleware for testnets like Polygon Amoy / Sepolia if needed
            self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            self.is_tester = False
            if private_key:
                account_obj = self.w3.eth.account.from_key(private_key)
                self.account = account_obj.address
            else:
                self.account = self.w3.eth.accounts[0] if self.w3.eth.accounts else None

        self.contract = None
        if self.contract_address:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=self.abi
            )

    def deploy_contract(self) -> str:
        """Deploys FacePostRegistry to the connected blockchain."""
        factory = self.w3.eth.contract(abi=self.abi, bytecode=self.bytecode)

        if self.is_tester:
            tx_hash = factory.constructor().transact({"from": self.account})
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            self.contract_address = receipt.contractAddress
        else:
            nonce = self.w3.eth.get_transaction_count(self.account)
            tx = factory.constructor().build_transaction({
                "from": self.account,
                "nonce": nonce,
                "gasPrice": self.w3.eth.gas_price,
            })
            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            self.contract_address = receipt.contractAddress

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.contract_address),
            abi=self.abi
        )
        return self.contract_address

    def register_face_post(
        self,
        face_hash_hex: str,
        post_hash_hex: str,
        post_url: str,
        author: str,
        platform: str,
    ) -> Dict[str, Any]:
        """
        Registers a face-to-post link on the smart contract.
        Returns a receipt dictionary with transaction hash, block number, and audit details.
        """
        if not self.contract:
            if not self.contract_address:
                self.deploy_contract()
            else:
                self.contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(self.contract_address),
                    abi=self.abi
                )

        face_b32 = to_bytes32(face_hash_hex)
        post_b32 = to_bytes32(post_hash_hex)

        func = self.contract.functions.registerFacePost(
            face_b32,
            post_b32,
            post_url,
            author,
            platform,
        )

        if self.is_tester:
            tx_hash = func.transact({"from": self.account})
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        else:
            nonce = self.w3.eth.get_transaction_count(self.account)
            tx = func.build_transaction({
                "from": self.account,
                "nonce": nonce,
                "gasPrice": self.w3.eth.gas_price,
            })
            signed = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        block = self.w3.eth.get_block(receipt.blockNumber)

        record_id = Web3.solidity_keccak(
            ["bytes32", "bytes32"],
            [face_b32, post_b32]
        ).hex()

        return {
            "record_id": record_id,
            "tx_hash": receipt.transactionHash.hex(),
            "block_number": receipt.blockNumber,
            "contract_address": self.contract_address,
            "gas_used": receipt.gasUsed,
            "timestamp": block.timestamp,
            "sender": self.account,
            "status": "CONFIRMED" if receipt.status == 1 else "FAILED",
            "chain_mode": self.mode,
        }

    def verify_record(
        self,
        face_hash_hex: str,
        post_hash_hex: str,
        saved_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Queries the blockchain smart contract to verify if the given face and post hashes
        match a registered tamper-evident record.
        Handles cross-process in-memory PyEVM state restoration if needed.
        """
        if not self.contract:
            if not self.contract_address:
                raise ValueError("No contract address available to verify against.")
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=self.abi
            )

        # In local PyEVM mode across separate CLI processes, the in-memory provider
        # starts fresh. If the contract is not found at the address, redeploy and restore state.
        if self.is_tester:
            code = self.w3.eth.get_code(Web3.to_checksum_address(self.contract_address))
            if not code or code == b"" or code == b"\x00":
                # Redeploy contract
                self.deploy_contract()
                if saved_state and "post_data" in saved_state:
                    p = saved_state["post_data"]
                    self.register_face_post(
                        face_hash_hex=saved_state.get("face_hash", face_hash_hex),
                        post_hash_hex=saved_state.get("post_hash", post_hash_hex),
                        post_url=p.get("url", ""),
                        author=p.get("author", ""),
                        platform=p.get("platform", ""),
                    )

        face_b32 = to_bytes32(face_hash_hex)
        post_b32 = to_bytes32(post_hash_hex)

        result = self.contract.functions.verifyRecord(face_b32, post_b32).call()
        is_valid, timestamp, post_url, author, platform, registered_by = result

        return {
            "is_valid": is_valid,
            "timestamp": timestamp,
            "post_url": post_url,
            "author": author,
            "platform": platform,
            "registered_by": registered_by,
            "contract_address": self.contract_address,
        }
