import AppKit
import Foundation
import ImageIO
import Vision

struct VisionReceipt: Codable {
    let path: String
    let width: Int
    let height: Int
    let faceCount: Int
    let primaryConfidence: Double?
    let boundingBox: [String: Double]?
    let yawRadians: Double?
    let landmarkCount: Int?
    let faceNearEdge: Bool?
    let faceIsSmall: Bool?
    let elapsedMilliseconds: Int
}

enum ReceiptError: Error {
    case unreadable(String)
}

func inspect(path: String) throws -> VisionReceipt {
    let started = ContinuousClock.now
    let url = URL(fileURLWithPath: path)
    guard
        let source = CGImageSourceCreateWithURL(url as CFURL, nil),
        let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
    else {
        throw ReceiptError.unreadable(path)
    }

    let request = VNDetectFaceLandmarksRequest()
    try VNImageRequestHandler(cgImage: image, orientation: .up).perform([request])
    let faces = request.results ?? []
    let primary = faces.max { $0.confidence < $1.confidence }
    let elapsed = started.duration(to: .now)
    let milliseconds = Int(
        elapsed.components.seconds * 1_000
            + elapsed.components.attoseconds / 1_000_000_000_000_000
    )

    return VisionReceipt(
        path: path,
        width: image.width,
        height: image.height,
        faceCount: faces.count,
        primaryConfidence: primary.map { Double($0.confidence) },
        boundingBox: primary.map {
            [
                "x": Double($0.boundingBox.minX),
                "y": Double($0.boundingBox.minY),
                "width": Double($0.boundingBox.width),
                "height": Double($0.boundingBox.height),
            ]
        },
        yawRadians: primary?.yaw?.doubleValue,
        landmarkCount: primary?.landmarks?.allPoints?.pointCount,
        faceNearEdge: primary.map {
            $0.boundingBox.minX < 0.015
                || $0.boundingBox.maxX > 0.985
                || $0.boundingBox.maxY > 0.985
        },
        faceIsSmall: primary.map {
            $0.boundingBox.width < 0.18 || $0.boundingBox.height < 0.18
        },
        elapsedMilliseconds: milliseconds
    )
}

let paths = Array(CommandLine.arguments.dropFirst())
guard !paths.isEmpty else {
    fputs("usage: swift scripts/local_vision_poc.swift IMAGE [IMAGE ...]\n", stderr)
    exit(2)
}

do {
    let receipts = try paths.map(inspect)
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
    FileHandle.standardOutput.write(try encoder.encode(receipts))
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fputs("local Vision PoC failed: \(error)\n", stderr)
    exit(1)
}
