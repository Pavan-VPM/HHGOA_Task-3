// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title FacePostRegistry
 * @dev Smart contract for anchoring and verifying face-to-social-media discoveries on-chain.
 * Provides a tamper-evident audit trail linking a facial biometric hash to discovered social media content.
 */
contract FacePostRegistry {
    struct FacePostRecord {
        bytes32 faceHash;
        bytes32 postHash;
        string postUrl;
        string author;
        string platform;
        uint256 timestamp;
        address registeredBy;
        bool exists;
    }

    // Mapping from composite recordId (hash(faceHash, postHash)) to Record
    mapping(bytes32 => FacePostRecord) public records;
    // Mapping from faceHash to array of recordIds associated with that face
    mapping(bytes32 => bytes32[]) private faceToRecords;
    // Array of all record IDs for auditability
    bytes32[] public allRecordIds;

    event FacePostRegistered(
        bytes32 indexed recordId,
        bytes32 indexed faceHash,
        bytes32 indexed postHash,
        string postUrl,
        string platform,
        address registeredBy,
        uint256 timestamp
    );

    /**
     * @notice Registers a new face-to-social-media link on the blockchain.
     * @param faceHash Cryptographic SHA-256/Keccak-256 fingerprint of the normalized face scan.
     * @param postHash Cryptographic fingerprint of the social media post content, media, and metadata.
     * @param postUrl Canonical URL of the discovered social media post.
     * @param author Social media username or author identifier.
     * @param platform Social platform name (e.g., 'twitter', 'reddit', 'instagram', 'linkedin').
     * @return recordId Unique composite identifier for this verification entry.
     */
    function registerFacePost(
        bytes32 faceHash,
        bytes32 postHash,
        string calldata postUrl,
        string calldata author,
        string calldata platform
    ) external returns (bytes32 recordId) {
        require(faceHash != bytes32(0), "Invalid face hash");
        require(postHash != bytes32(0), "Invalid post hash");
        require(bytes(postUrl).length > 0, "Post URL cannot be empty");

        recordId = keccak256(abi.encodePacked(faceHash, postHash));
        require(!records[recordId].exists, "Record already registered");

        records[recordId] = FacePostRecord({
            faceHash: faceHash,
            postHash: postHash,
            postUrl: postUrl,
            author: author,
            platform: platform,
            timestamp: block.timestamp,
            registeredBy: msg.sender,
            exists: true
        });

        faceToRecords[faceHash].push(recordId);
        allRecordIds.push(recordId);

        emit FacePostRegistered(
            recordId,
            faceHash,
            postHash,
            postUrl,
            platform,
            msg.sender,
            block.timestamp
        );

        return recordId;
    }

    /**
     * @notice Verifies whether a given face hash and post hash have been registered on-chain.
     * @param faceHash The face scan fingerprint to verify.
     * @param postHash The post content fingerprint to verify.
     * @return isValid True if the exact pair exists on-chain and has not been altered.
     * @return timestamp The block timestamp when the record was registered.
     * @return postUrl The stored canonical post URL.
     * @return author The stored author.
     * @return platform The social media platform.
     * @return registeredBy The Ethereum address that signed the registration transaction.
     */
    function verifyRecord(
        bytes32 faceHash,
        bytes32 postHash
    )
        external
        view
        returns (
            bool isValid,
            uint256 timestamp,
            string memory postUrl,
            string memory author,
            string memory platform,
            address registeredBy
        )
    {
        bytes32 recordId = keccak256(abi.encodePacked(faceHash, postHash));
        FacePostRecord memory rec = records[recordId];

        if (!rec.exists) {
            return (false, 0, "", "", "", address(0));
        }

        return (
            true,
            rec.timestamp,
            rec.postUrl,
            rec.author,
            rec.platform,
            rec.registeredBy
        );
    }

    /**
     * @notice Returns total number of registered records.
     */
    function getRecordCount() external view returns (uint256) {
        return allRecordIds.length;
    }

    /**
     * @notice Returns all record IDs associated with a specific face hash.
     */
    function getRecordsByFace(bytes32 faceHash) external view returns (bytes32[] memory) {
        return faceToRecords[faceHash];
    }
}
