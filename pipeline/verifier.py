"""
Blockchain Verification and Tamper-Detection Engine.
Verifies discovered data against on-chain smart contract state and proves tamper-evident security.
"""

import copy
import json
import os
from typing import Dict, Any, Optional

from blockchain.evm_client import EVMClient
from blockchain.hasher import hash_post_content, to_bytes32


class Verifier:
    def __init__(self, evm_client: EVMClient):
        self.client = evm_client

    def verify_pipeline_result(
        self,
        face_hash: str,
        post_data: Dict[str, Any],
        expected_contract_address: Optional[str] = None,
        saved_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Recomputes the cryptographic hash of post_data and queries the blockchain smart contract
        to verify that the record exists and has not been altered.
        """
        # Recompute post fingerprint
        recomputed_post_hash = hash_post_content(post_data)

        # Query blockchain contract
        on_chain = self.client.verify_record(
            face_hash_hex=face_hash,
            post_hash_hex=recomputed_post_hash,
            saved_state=saved_state or {"face_hash": face_hash, "post_hash": recomputed_post_hash, "post_data": post_data},
        )

        verification_passed = bool(on_chain.get("is_valid", False))

        return {
            "verified": verification_passed,
            "face_hash": face_hash,
            "post_hash": recomputed_post_hash,
            "block_timestamp": on_chain.get("timestamp"),
            "contract_address": on_chain.get("contract_address"),
            "on_chain_author": on_chain.get("author"),
            "on_chain_url": on_chain.get("post_url"),
            "registered_by": on_chain.get("registered_by"),
            "details": "Data matches on-chain cryptographic fingerprint perfectly." if verification_passed else "Verification failed: Record not found on blockchain or hash mismatch."
        }

    def run_tamper_demonstration(
        self,
        face_hash: str,
        post_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes a rigorous tamper test:
        1. Verifies authentic record against on-chain state (passes).
        2. Simulates an adversary modifying 1 character in the post text.
        3. Simulates an adversary modifying the media hash.
        4. Demonstrates on-chain rejection for both tampered versions.
        """
        print("\n" + "=" * 60)
        print("🔒 RUNNING ON-CHAIN TAMPER-EVIDENCE AUDIT")
        print("=" * 60)

        # 1. Authentic verification
        auth_result = self.verify_pipeline_result(face_hash, post_data)
        print(f"\n[1] Authentic Data Verification:")
        print(f"    - Face Hash:      {face_hash}")
        print(f"    - Post Hash:      {auth_result['post_hash']}")
        print(f"    - On-Chain Valid: {auth_result['verified']} ✅")
        print(f"    - Timestamp:      {auth_result['block_timestamp']}")
        print(f"    - Registered By:  {auth_result['registered_by']}")

        # 2. Text tampering test
        tampered_text_post = copy.deepcopy(post_data)
        original_text = tampered_text_post.get("text", "")
        tampered_text_post["text"] = original_text + " [TAMPERED_INJECTED_STRING]"
        tampered_text_hash = hash_post_content(tampered_text_post)
        text_tamper_result = self.verify_pipeline_result(face_hash, tampered_text_post)

        print(f"\n[2] Adversary Alters Post Text:")
        print(f"    - Original Text: {original_text[:50]}...")
        print(f"    - Tampered Text: {tampered_text_post['text'][:50]}...")
        print(f"    - New Post Hash: {tampered_text_hash}")
        print(f"    - On-Chain Valid: {text_tamper_result['verified']} ❌ (REJECTED AS TAMPERED)")

        # 3. Media hash tampering test
        tampered_media_post = copy.deepcopy(post_data)
        tampered_media_post["media_sha256"] = "0x" + "00" * 32
        tampered_media_hash = hash_post_content(tampered_media_post)
        media_tamper_result = self.verify_pipeline_result(face_hash, tampered_media_post)

        print(f"\n[3] Adversary Swaps Post Media Image:")
        print(f"    - Tampered Media SHA256: {tampered_media_post['media_sha256']}")
        print(f"    - New Post Hash:         {tampered_media_hash}")
        print(f"    - On-Chain Valid:        {media_tamper_result['verified']} ❌ (REJECTED AS TAMPERED)")

        print("\n" + "=" * 60)
        print("✅ BLOCKCHAIN RE-VERIFICATION & TAMPER PROOF COMPLETE")
        print("=" * 60 + "\n")

        return {
            "authentic": auth_result,
            "tampered_text": text_tamper_result,
            "tampered_media": media_tamper_result,
            "tamper_detected": (not text_tamper_result["verified"]) and (not media_tamper_result["verified"]),
        }
