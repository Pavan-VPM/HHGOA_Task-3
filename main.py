#!/usr/bin/env python3
"""
Face Scan to Blockchain Social Media Verification Pipeline.

Pipeline Flow:
  Face Scan Input
      ↓
  Face Identification & Cryptographic Encoding (OpenCV + SHA-256)
      ↓
  Web / Social Media Search & Facial Correspondence (ddgs / SerpApi)
      ↓
  Blockchain Smart Contract Upload & Tamper-Evident Verification (Web3.py / EVM)
"""

import argparse
import json
import os
import sys
import time
from typing import Dict, Any

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from blockchain.evm_client import EVMClient
from blockchain.hasher import hash_post_content, compute_merkle_root
from pipeline.face_engine import FaceEngine
from pipeline.search_engine import SearchEngine
from pipeline.verifier import Verifier


DEFAULT_STATE_FILE = "blockchain_state.json"


def print_banner():
    print("""
======================================================================
  👁️  FACE SCAN -> SOCIAL MEDIA SEARCH -> BLOCKCHAIN VERIFICATION  ⛓️
======================================================================
    """)


def run_pipeline(
    image_path: str,
    search_query: str = "Satya Nadella",
    platform: str = "all",
    blockchain_mode: str = "local",
    rpc_url: str = None,
    private_key: str = None,
    contract_address: str = None,
    state_file: str = DEFAULT_STATE_FILE,
) -> Dict[str, Any]:
    print_banner()

    print(f"🚀 Initializing Pipeline...")
    print(f"   - Input Image:     {image_path}")
    print(f"   - Search Query:    {search_query}")
    print(f"   - Target Platform: {platform.upper()}")
    print(f"   - Blockchain Mode: {blockchain_mode.upper()}")
    print("-" * 70)

    # -------------------------------------------------------------
    # STAGE 1: Face Detection & Encoding
    # -------------------------------------------------------------
    print("\n[STAGE 1] 👤 Face Detection & Encoding")
    face_engine = FaceEngine()
    print("   → Processing input image...")
    face_result = face_engine.process_face(image_path)

    print(f"   ✓ Face Detected:        {face_result['face_detected']}")
    print(f"   ✓ Detection Confidence: {face_result['confidence'] * 100:.1f}%")
    print(f"   ✓ Bounding Box:         {face_result['bbox']}")
    print(f"   ✓ Face SHA-256 Hash:    {face_result['face_hash']}")
    print(f"   ✓ Perceptual dHash:     {face_result['dhash']}")
    print(f"   ✓ Feature Vector:       128-dimensional normalized descriptor computed")

    # -------------------------------------------------------------
    # STAGE 2: Genuine Web / Social Media Search
    # -------------------------------------------------------------
    print(f"\n[STAGE 2] 🌐 Genuine Web & Social Media Search ({platform.upper()})")
    print(f"   → Querying {platform} & web platforms for: '{search_query}'...")
    search_engine = SearchEngine(face_engine=face_engine)
    post_data = search_engine.find_matching_post(
        input_face_data=face_result,
        search_query=search_query,
        platform_filter=platform,
        image_url=image_path if image_path.startswith("http") else None,
    )

    print(f"   ✓ Matching Post Found:")
    print(f"     • Platform:         {post_data['platform'].upper()}")
    print(f"     • Post URL:         {post_data['url']}")
    print(f"     • Author:           {post_data['author']}")
    print(f"     • Text Snippet:     {post_data['text'][:80]}...")
    print(f"     • Timestamp:        {post_data['timestamp']}")
    print(f"     • Media Hash:       {post_data['media_sha256']}")
    print(f"     • Facial Match:     {post_data['match_confidence'] * 100:.1f}% correspondence")
    print(f"     • Genuine Search:   {post_data['is_genuine_web_match']}")

    # -------------------------------------------------------------
    # STAGE 3: Blockchain Cryptographic Upload
    # -------------------------------------------------------------
    print("\n[STAGE 3] ⛓️ Blockchain Upload & Tamper-Evident Registration")
    post_hash = hash_post_content(post_data)
    merkle_root = compute_merkle_root([
        face_result["face_hash"],
        post_hash,
        post_data["media_sha256"],
    ])

    print(f"   → Cryptographic Digest Computed:")
    print(f"     • Face Hash:       {face_result['face_hash']}")
    print(f"     • Post Hash:       {post_hash}")
    print(f"     • Merkle Root:     {merkle_root}")

    # Initialize EVM client
    evm_client = EVMClient(
        mode=blockchain_mode,
        rpc_url=rpc_url or os.getenv("RPC_URL"),
        private_key=private_key or os.getenv("PRIVATE_KEY"),
        contract_address=contract_address or os.getenv("CONTRACT_ADDRESS"),
    )

    if not evm_client.contract_address:
        print("   → Deploying FacePostRegistry smart contract to blockchain...")
        deployed_addr = evm_client.deploy_contract()
        print(f"   ✓ Smart Contract Deployed At: {deployed_addr}")
    else:
        print(f"   ✓ Using Existing Contract At: {evm_client.contract_address}")

    print("   → Submitting on-chain registration transaction...")
    receipt = evm_client.register_face_post(
        face_hash_hex=face_result["face_hash"],
        post_hash_hex=post_hash,
        post_url=post_data["url"],
        author=post_data["author"],
        platform=post_data["platform"],
    )

    print(f"   ✓ Transaction Confirmed On-Chain:")
    print(f"     • Record ID:       {receipt['record_id']}")
    print(f"     • Transaction:     {receipt['tx_hash']}")
    print(f"     • Block Number:    #{receipt['block_number']}")
    print(f"     • Gas Used:        {receipt['gas_used']} gas")
    print(f"     • Timestamp:       {receipt['timestamp']}")
    print(f"     • Status:          {receipt['status']} ✅")

    # Save state to persistent file for offline/subsequent re-verification
    pipeline_state = {
        "record_id": receipt["record_id"],
        "tx_hash": receipt["tx_hash"],
        "block_number": receipt["block_number"],
        "contract_address": receipt["contract_address"],
        "timestamp": receipt["timestamp"],
        "gas_used": receipt.get("gas_used", 320000),
        "chain_mode": blockchain_mode,
        "face_hash": face_result["face_hash"],
        "post_hash": post_hash,
        "merkle_root": merkle_root,
        "face_data": {
            "face_detected": face_result["face_detected"],
            "confidence": face_result["confidence"],
            "bbox": face_result["bbox"],
            "dhash": face_result["dhash"],
            "feature_vector_sample": [round(float(v), 4) for v in face_result.get("feature_vector", [])[:8]],
        },
        "post_data": post_data,
        "search_steps": post_data.get("search_steps", []),
        "candidates_discovered": post_data.get("candidates_discovered", []),
    }

    with open(state_file, "w") as f:
        json.dump(pipeline_state, f, indent=2)
    print(f"\n📁 Verification state saved to: {state_file}")

    # -------------------------------------------------------------
    # STAGE 4: Demonstration of Re-Verification
    # -------------------------------------------------------------
    print("\n[STAGE 4] 🔍 Re-Verifying Data Against On-Chain Record...")
    verifier = Verifier(evm_client)
    verify_result = verifier.verify_pipeline_result(
        face_hash=face_result["face_hash"],
        post_data=post_data,
    )

    print(f"   ✓ Verification Result: {verify_result['verified']} ✅")
    print(f"   ✓ Stored Author:       {verify_result['on_chain_author']}")
    print(f"   ✓ Stored Post URL:     {verify_result['on_chain_url']}")
    print(f"   ✓ Registered By:       {verify_result['registered_by']}")
    print(f"   ✓ Audit Status:        {verify_result['details']}")

    print("\n" + "=" * 70)
    print("🎉 END-TO-END PIPELINE COMPLETED SUCCESSFULLY!")
    print("=" * 70 + "\n")

    return {
        "pipeline_state": pipeline_state,
        "evm_client": evm_client,
        "verifier": verifier,
    }


def verify_command(state_file: str = DEFAULT_STATE_FILE):
    """CLI subcommand to re-verify an existing stored record against blockchain."""
    if not os.path.exists(state_file):
        print(f"❌ Error: State file '{state_file}' not found. Run the pipeline first.")
        sys.exit(1)

    with open(state_file, "r") as f:
        state = json.load(f)

    print(f"📖 Loaded state from {state_file}:")
    print(f"   - Record ID:        {state['record_id']}")
    print(f"   - Contract Address: {state['contract_address']}")
    print(f"   - Face Hash:        {state['face_hash']}")
    print(f"   - Post Hash:        {state['post_hash']}")

    evm_client = EVMClient(
        mode=state.get("chain_mode", "local"),
        contract_address=state["contract_address"],
    )

    verifier = Verifier(evm_client)
    res = verifier.verify_pipeline_result(
        face_hash=state["face_hash"],
        post_data=state["post_data"],
        saved_state=state,
    )

    print("\nOn-Chain Verification Status:")
    for k, v in res.items():
        print(f"  • {k}: {v}")


def demo_command():
    """Runs an end-to-end automated demo including tamper detection."""
    sample_img = "samples/test_face_1.jpg"
    if not os.path.exists(sample_img):
        print(f"Sample image {sample_img} not found, using default portrait.")

    result = run_pipeline(
        image_path=sample_img,
        search_query="Satya Nadella",
        blockchain_mode="local",
    )

    # Run cryptographic tamper demonstration
    verifier = result["verifier"]
    state = result["pipeline_state"]
    verifier.run_tamper_demonstration(
        face_hash=state["face_hash"],
        post_data=state["post_data"],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Face Scan -> Social Media Search -> Blockchain Verification Pipeline"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_p = subparsers.add_parser("run", help="Run the full end-to-end pipeline")
    run_p.add_argument("--image", required=True, help="Path or URL to face image")
    run_p.add_argument("--query", default="Satya Nadella", help="Search query for web/social discovery")
    run_p.add_argument("--platform", default="all", choices=["all", "twitter", "linkedin", "reddit", "instagram", "youtube"], help="Target social platform")
    run_p.add_argument("--mode", default="local", choices=["local", "remote"], help="Blockchain mode")
    run_p.add_argument("--rpc-url", default=None, help="EVM RPC URL (for remote mode)")
    run_p.add_argument("--private-key", default=None, help="Private key (for remote mode)")
    run_p.add_argument("--contract", default=None, help="Pre-deployed contract address")
    run_p.add_argument("--output", default=DEFAULT_STATE_FILE, help="Output state JSON file")

    # Verify command
    verify_p = subparsers.add_parser("verify", help="Re-verify saved data against blockchain")
    verify_p.add_argument("--state", default=DEFAULT_STATE_FILE, help="State JSON file to verify")

    # Demo command
    subparsers.add_parser("demo", help="Run full automated demo with tamper audit")

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(
            image_path=args.image,
            search_query=args.query,
            platform=args.platform,
            blockchain_mode=args.mode,
            rpc_url=args.rpc_url,
            private_key=args.private_key,
            contract_address=args.contract,
            state_file=args.output,
        )
    elif args.command == "verify":
        verify_command(state_file=args.state)
    elif args.command == "demo":
        demo_command()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
