"""
Comprehensive Automated Test Suite for Face Scan -> Social Search -> Blockchain Verification Pipeline.
"""

import os
import unittest
import numpy as np

from blockchain.hasher import (
    hash_face_array,
    hash_post_content,
    compute_merkle_root,
    to_bytes32,
    sha256_hex,
)
from blockchain.evm_client import EVMClient
from pipeline.face_engine import FaceEngine
from pipeline.search_engine import SearchEngine
from pipeline.verifier import Verifier


class TestHasher(unittest.TestCase):
    def test_to_bytes32(self):
        h = "0x" + "ab" * 32
        b = to_bytes32(h)
        self.assertEqual(len(b), 32)
        self.assertEqual(b[0], 0xAB)

    def test_merkle_root_computation(self):
        leaf1 = sha256_hex(b"face_data")
        leaf2 = sha256_hex(b"post_data")
        leaf3 = sha256_hex(b"media_data")
        root = compute_merkle_root([leaf1, leaf2, leaf3])
        self.assertTrue(root.startswith("0x"))
        self.assertEqual(len(root), 66)

    def test_post_hash_determinism(self):
        post_a = {
            "platform": "twitter",
            "url": "https://x.com/example/status/1",
            "author": "@example",
            "text": "Hello world",
            "timestamp": 1700000000,
            "media_sha256": "0x1234",
        }
        post_b = dict(post_a)
        self.assertEqual(hash_post_content(post_a), hash_post_content(post_b))

        # Changing text changes hash
        post_c = dict(post_a)
        post_c["text"] = "Hello world modified"
        self.assertNotEqual(hash_post_content(post_a), hash_post_content(post_c))


class TestFaceEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FaceEngine()
        cls.sample_path = "samples/test_face_1.jpg"

    def test_face_detection_and_encoding(self):
        result = self.engine.process_face(self.sample_path)
        self.assertTrue(result["face_detected"])
        self.assertIn("face_hash", result)
        self.assertTrue(result["face_hash"].startswith("0x"))
        self.assertEqual(len(result["feature_vector"]), 128)
        self.assertGreater(len(result["dhash"]), 0)

    def test_face_comparison(self):
        f1 = self.engine.process_face(self.sample_path)
        comp_self = self.engine.compare_faces(f1, f1)
        self.assertTrue(comp_self["is_match"])
        self.assertEqual(comp_self["composite_score"], 1.0)
        self.assertTrue(comp_self["exact_cryptographic_match"])


class TestSearchEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SearchEngine()

    def test_platform_detection(self):
        self.assertEqual(self.engine.detect_platform("https://x.com/user/status/123"), "twitter")
        self.assertEqual(self.engine.detect_platform("https://reddit.com/r/tech"), "reddit")
        self.assertEqual(self.engine.detect_platform("https://linkedin.com/in/user"), "linkedin")

    def test_social_url_check(self):
        self.assertTrue(self.engine.is_social_url("https://twitter.com/satyanadella"))
        self.assertTrue(self.engine.is_social_url("https://reddit.com/r/all"))
        self.assertFalse(self.engine.is_social_url("https://example.org/news"))


class TestBlockchainEVM(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = EVMClient(mode="local")
        cls.contract_addr = cls.client.deploy_contract()

    def test_contract_deployment(self):
        self.assertTrue(self.contract_addr.startswith("0x"))
        self.assertEqual(len(self.contract_addr), 42)

    def test_registration_and_tamper_verification(self):
        face_hash = sha256_hex(b"biometric_face_scan_test")
        post_data = {
            "platform": "twitter",
            "url": "https://twitter.com/test/status/999",
            "author": "@test",
            "text": "Blockchain verification test post",
            "timestamp": 1780000000,
            "media_sha256": sha256_hex(b"media_bytes"),
        }
        post_hash = hash_post_content(post_data)

        # Register
        receipt = self.client.register_face_post(
            face_hash_hex=face_hash,
            post_hash_hex=post_hash,
            post_url=post_data["url"],
            author=post_data["author"],
            platform=post_data["platform"],
        )
        self.assertEqual(receipt["status"], "CONFIRMED")
        self.assertGreater(receipt["block_number"], 0)

        # Verify authentic
        verifier = Verifier(self.client)
        auth_res = verifier.verify_pipeline_result(face_hash, post_data)
        self.assertTrue(auth_res["verified"])
        self.assertEqual(auth_res["on_chain_author"], "@test")

        # Verify tampered
        tampered_data = dict(post_data)
        tampered_data["text"] = "Altered text statement"
        tamper_res = verifier.verify_pipeline_result(face_hash, tampered_data)
        self.assertFalse(tamper_res["verified"])


if __name__ == "__main__":
    unittest.main()
