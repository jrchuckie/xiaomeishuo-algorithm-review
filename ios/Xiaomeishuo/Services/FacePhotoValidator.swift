import Foundation
import UIKit
import Vision

enum FacePhotoRole {
    case general
    case front
    case angle45
}

enum FacePhotoValidationError: LocalizedError {
    case unreadable
    case noFace
    case multipleFaces
    case blurry
    case tooDark
    case overexposed
    case faceTooCloseToEdge
    case occluded
    case notFront
    case notAngle
    case duplicatePair

    var errorDescription: String? {
        switch self {
        case .unreadable:
            String(localized: "这张照片无法读取，请换一张清晰照片。")
        case .noFace:
            String(localized: "没有识别到清晰人脸，请选择无遮挡的本人照片。")
        case .multipleFaces:
            String(localized: "请使用只有你一个人的照片。")
        case .blurry:
            String(localized: "照片有明显模糊，请保持手机稳定后重拍。")
        case .tooDark:
            String(localized: "照片太暗，请面向自然光后重拍。")
        case .overexposed:
            String(localized: "照片过曝，请避开强光后重拍。")
        case .faceTooCloseToEdge:
            String(localized: "脸或头发太贴近画面边缘，请稍微退后一点重拍。")
        case .occluded:
            String(localized: "五官有明显遮挡，请露出完整面部后重拍。")
        case .notFront:
            String(localized: "正面照角度不正，请直视镜头后重拍。")
        case .notAngle:
            String(localized: "45° 照角度不足，请把脸轻轻转向一侧后重拍。")
        case .duplicatePair:
            String(localized: "正面照和 45° 照似乎是同一张，请重新选择第二张。")
        }
    }
}

enum FacePhotoValidationNotice: Hashable {
    case faceIsSmall

    var message: String {
        switch self {
        case .faceIsSmall:
            String(localized: "已识别人脸，会继续生成。因为人物在画面中较小，局部细节调整可能不如近景照片精细。")
        }
    }
}

struct FacePhotoValidationResult {
    let notices: Set<FacePhotoValidationNotice>

    var noticeMessage: String? {
        let messages = notices.map(\.message).sorted()
        return messages.isEmpty ? nil : messages.joined(separator: "\n")
    }
}

private struct FacePhotoObservation {
    let face: VNFaceObservation
    let featurePrint: VNFeaturePrintObservation?
    let notices: Set<FacePhotoValidationNotice>
}

enum FacePhotoValidator {
    static func validate(
        at url: URL,
        role: FacePhotoRole = .general
    ) async throws -> FacePhotoValidationResult {
        let observation = try await inspect(at: url, role: role)
        return FacePhotoValidationResult(notices: observation.notices)
    }

    static func validatePair(
        front: URL,
        angle45: URL
    ) async throws -> FacePhotoValidationResult {
        async let frontObservation = inspect(at: front, role: .front)
        async let angleObservation = inspect(at: angle45, role: .angle45)
        let (frontResult, angleResult) = try await (frontObservation, angleObservation)

        if
            let first = frontResult.featurePrint,
            let second = angleResult.featurePrint
        {
            var distance: Float = 1
            try first.computeDistance(&distance, to: second)
            let yawDelta = abs(yaw(frontResult.face) - yaw(angleResult.face))
            if distance < 0.015 && yawDelta < 0.08 {
                throw FacePhotoValidationError.duplicatePair
            }
        }
        return FacePhotoValidationResult(
            notices: frontResult.notices.union(angleResult.notices)
        )
    }

    private static func inspect(
        at url: URL,
        role: FacePhotoRole
    ) async throws -> FacePhotoObservation {
        guard
            let data = try? Data(contentsOf: url),
            let image = UIImage(data: data),
            let cgImage = image.cgImage,
            cgImage.width >= 640,
            cgImage.height >= 640
        else {
            throw FacePhotoValidationError.unreadable
        }

        let luminance = try luminancePixels(from: cgImage)
        let mean = Double(luminance.reduce(0) { $0 + Int($1) }) / Double(luminance.count)
        let darkShare = Double(luminance.filter { $0 < 10 }.count) / Double(luminance.count)
        let brightShare = Double(luminance.filter { $0 > 245 }.count) / Double(luminance.count)
        if mean < 42 || darkShare > 0.58 { throw FacePhotoValidationError.tooDark }
        if mean > 222 || brightShare > 0.58 { throw FacePhotoValidationError.overexposed }
        if laplacianVariance(luminance) < 42 { throw FacePhotoValidationError.blurry }

        let observations = try await visionObservations(cgImage: cgImage)
        guard !observations.faces.isEmpty else { throw FacePhotoValidationError.noFace }
        guard observations.faces.count == 1 else { throw FacePhotoValidationError.multipleFaces }
        guard let face = observations.faces.first else {
            throw FacePhotoValidationError.noFace
        }
        let faceIsSmall =
            face.boundingBox.width < 0.18
            || face.boundingBox.height < 0.18
        let notices: Set<FacePhotoValidationNotice> =
            faceIsSmall ? [.faceIsSmall] : []
        if
            face.boundingBox.minX < 0.015
                || face.boundingBox.maxX > 0.985
                || face.boundingBox.maxY > 0.985
        {
            throw FacePhotoValidationError.faceTooCloseToEdge
        }
        if faceIsSmall {
            // Vision can detect a valid distant face without returning dense landmarks.
            // Treat this as lower-confidence input, not as proof of occlusion.
            guard face.confidence >= 0.35 else {
                throw FacePhotoValidationError.occluded
            }
        } else {
            guard
                face.confidence >= 0.65,
                let landmarks = face.landmarks,
                landmarks.allPoints?.pointCount ?? 0 >= 45
            else {
                throw FacePhotoValidationError.occluded
            }
        }

        let absoluteYaw = abs(yaw(face))
        // A distant face may not have a reliable yaw estimate. Do not turn missing
        // precision into a rejection; the cloud model can still use the full image.
        if !faceIsSmall {
            switch role {
            case .general:
                break
            case .front where absoluteYaw > 0.30:
                throw FacePhotoValidationError.notFront
            case .angle45 where absoluteYaw < 0.18 || absoluteYaw > 1.05:
                throw FacePhotoValidationError.notAngle
            default:
                break
            }
        }
        return FacePhotoObservation(
            face: face,
            featurePrint: observations.featurePrint,
            notices: notices
        )
    }

    private static func visionObservations(
        cgImage: CGImage
    ) async throws -> (faces: [VNFaceObservation], featurePrint: VNFeaturePrintObservation?) {
        try await withCheckedThrowingContinuation { continuation in
            let faceRequest = VNDetectFaceLandmarksRequest()
            let featureRequest = VNGenerateImageFeaturePrintRequest()
            do {
                try VNImageRequestHandler(cgImage: cgImage).perform([faceRequest, featureRequest])
                continuation.resume(
                    returning: (
                        faceRequest.results ?? [],
                        featureRequest.results?.first
                    )
                )
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }

    private static func yaw(_ face: VNFaceObservation) -> Double {
        face.yaw?.doubleValue ?? 0
    }

    private static func luminancePixels(from image: CGImage) throws -> [UInt8] {
        let width = 128
        let height = 128
        var pixels = [UInt8](repeating: 0, count: width * height)
        guard
            let context = CGContext(
                data: &pixels,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: width,
                space: CGColorSpaceCreateDeviceGray(),
                bitmapInfo: CGImageAlphaInfo.none.rawValue
            )
        else {
            throw FacePhotoValidationError.unreadable
        }
        context.interpolationQuality = .medium
        context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
        return pixels
    }

    private static func laplacianVariance(_ pixels: [UInt8]) -> Double {
        let width = 128
        var values: [Double] = []
        values.reserveCapacity((width - 2) * (width - 2))
        for y in 1..<(width - 1) {
            for x in 1..<(width - 1) {
                let center = Double(pixels[y * width + x])
                let laplacian =
                    Double(pixels[(y - 1) * width + x])
                    + Double(pixels[(y + 1) * width + x])
                    + Double(pixels[y * width + x - 1])
                    + Double(pixels[y * width + x + 1])
                    - 4 * center
                values.append(laplacian)
            }
        }
        let mean = values.reduce(0, +) / Double(values.count)
        return values.reduce(0) { $0 + pow($1 - mean, 2) } / Double(values.count)
    }
}
