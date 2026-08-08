import Foundation
import UIKit

enum APIError: LocalizedError {
    case invalidResponse
    case invalidImage
    case server(String)
    case network

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return String(localized: "服务返回了无法识别的结果。")
        case .invalidImage:
            return String(localized: "这张照片暂时无法读取，请换一张再试。")
        case .server(let message):
            return message
        case .network:
            return String(localized: "暂时连接不到小美说 AI 服务，请检查网络后重试。")
        }
    }
}

actor APIClient {
    static let shared = APIClient()

    private let session = URLSession.shared

    func previewBoard(url: String) async throws -> BoardPreviewDTO {
        var request = try makeRequest(path: "/api/v1/boards/preview", method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder.api.encode(BoardPreviewRequestDTO(url: url))
        return try await send(request, as: BoardPreviewDTO.self)
    }

    func createProfile(
        referenceURLs: [URL],
        calibrationHistory: [String] = []
    ) async throws -> AestheticProfileDTO {
        let boundary = UUID().uuidString
        var request = try makeRequest(path: "/api/v1/aesthetic/profile", method: "POST")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        for (index, url) in referenceURLs.enumerated() {
            let data = try uploadJPEGData(at: url, maxDimension: 1280, quality: 0.78)
            body.appendFile(
                data,
                name: "references",
                filename: "reference-\(index + 1).jpg",
                mimeType: "image/jpeg",
                boundary: boundary
            )
        }
        body.appendField(
            name: "calibration_json",
            value: String(
                data: try JSONSerialization.data(
                    withJSONObject: Array(calibrationHistory.suffix(12))
                ),
                encoding: .utf8
            ) ?? "[]",
            boundary: boundary
        )
        body.append("--\(boundary)--\r\n")
        request.httpBody = body
        return try await send(request, as: AestheticProfileDTO.self)
    }

    func createEditPlan(
        sourceURL: URL,
        profile: AestheticProfileDTO,
        intensity: APIIntensity
    ) async throws -> EditPlanDTO {
        let boundary = UUID().uuidString
        var request = try makeRequest(path: "/api/v1/edits/plan", method: "POST")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        body.appendFile(
            try uploadJPEGData(at: sourceURL, maxDimension: 2048, quality: 0.92),
            name: "source",
            filename: "source.jpg",
            mimeType: "image/jpeg",
            boundary: boundary
        )
        body.appendField(
            name: "profile_json",
            value: String(data: try JSONEncoder.api.encode(profile), encoding: .utf8) ?? "{}",
            boundary: boundary
        )
        body.appendField(name: "intensity", value: intensity.rawValue, boundary: boundary)
        body.append("--\(boundary)--\r\n")
        request.httpBody = body
        return try await send(request, as: EditPlanDTO.self)
    }

    func generate(
        sourceURL: URL,
        plan: EditPlanDTO,
        previousResultURL: URL? = nil,
        feedback: String? = nil
    ) async throws -> GenerationResultDTO {
        let boundary = UUID().uuidString
        var request = try makeRequest(path: "/api/v1/edits/generate", method: "POST")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        body.appendFile(
            try uploadJPEGData(at: sourceURL, maxDimension: 3072, quality: 0.95),
            name: "source",
            filename: "source.jpg",
            mimeType: "image/jpeg",
            boundary: boundary
        )
        body.appendField(
            name: "plan_json",
            value: String(data: try JSONEncoder.api.encode(plan), encoding: .utf8) ?? "{}",
            boundary: boundary
        )
        if let previousResultURL {
            body.appendFile(
                try uploadJPEGData(at: previousResultURL, maxDimension: 3072, quality: 0.95),
                name: "previous_result",
                filename: "previous-result.jpg",
                mimeType: "image/jpeg",
                boundary: boundary
            )
        }
        if let feedback, !feedback.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            body.appendField(name: "feedback", value: feedback, boundary: boundary)
        }
        body.append("--\(boundary)--\r\n")
        request.httpBody = body
        request.timeoutInterval = 540
        return try await send(request, as: GenerationResultDTO.self)
    }

    func createMedicalPlan(
        frontURL: URL,
        sideURL: URL?,
        profile: AestheticProfileDTO,
        preferences: [String: String],
        selectedDirections: [String],
        intensity: MedicalIntensity
    ) async throws -> MedicalPlanDTO {
        let boundary = UUID().uuidString
        var request = try makeRequest(path: "/api/v1/medical/plan", method: "POST")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        body.appendFile(
            try uploadJPEGData(at: frontURL, maxDimension: 2048, quality: 0.94),
            name: "front",
            filename: "front.jpg",
            mimeType: "image/jpeg",
            boundary: boundary
        )
        if let sideURL {
            body.appendFile(
                try uploadJPEGData(at: sideURL, maxDimension: 2048, quality: 0.94),
                name: "side",
                filename: "side.jpg",
                mimeType: "image/jpeg",
                boundary: boundary
            )
        }
        body.appendField(
            name: "profile_json",
            value: String(data: try JSONEncoder.api.encode(profile), encoding: .utf8) ?? "{}",
            boundary: boundary
        )
        body.appendField(
            name: "preferences_json",
            value: String(
                data: try JSONSerialization.data(withJSONObject: preferences),
                encoding: .utf8
            ) ?? "{}",
            boundary: boundary
        )
        body.appendField(
            name: "selected_directions_json",
            value: String(
                data: try JSONSerialization.data(withJSONObject: selectedDirections),
                encoding: .utf8
            ) ?? "[]",
            boundary: boundary
        )
        body.appendField(name: "intensity", value: intensity.rawValue, boundary: boundary)
        body.append("--\(boundary)--\r\n")
        request.httpBody = body
        request.timeoutInterval = 240
        return try await send(request, as: MedicalPlanDTO.self)
    }

    func generateMedical(
        sourceURL: URL,
        plan: MedicalPlanDTO,
        intensity: MedicalIntensity,
        previousResultURL: URL? = nil,
        feedback: String? = nil
    ) async throws -> GenerationResultDTO {
        let boundary = UUID().uuidString
        var request = try makeRequest(path: "/api/v1/medical/generate", method: "POST")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var body = Data()
        body.appendFile(
            try uploadJPEGData(at: sourceURL, maxDimension: 3072, quality: 0.95),
            name: "source",
            filename: "front.jpg",
            mimeType: "image/jpeg",
            boundary: boundary
        )
        body.appendField(
            name: "plan_json",
            value: String(data: try JSONEncoder.api.encode(plan), encoding: .utf8) ?? "{}",
            boundary: boundary
        )
        body.appendField(name: "intensity", value: intensity.rawValue, boundary: boundary)
        if let previousResultURL {
            body.appendFile(
                try uploadJPEGData(at: previousResultURL, maxDimension: 3072, quality: 0.95),
                name: "previous_result",
                filename: "previous-result.jpg",
                mimeType: "image/jpeg",
                boundary: boundary
            )
        }
        if let feedback, !feedback.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            body.appendField(name: "feedback", value: feedback, boundary: boundary)
        }
        body.append("--\(boundary)--\r\n")
        request.httpBody = body
        request.timeoutInterval = 540
        return try await send(request, as: GenerationResultDTO.self)
    }

    private func uploadJPEGData(
        at url: URL,
        maxDimension: CGFloat,
        quality: CGFloat
    ) throws -> Data {
        let sourceData = try Data(contentsOf: url)
        guard let image = UIImage(data: sourceData) else {
            throw APIError.invalidImage
        }

        let sourceMaxDimension = max(image.size.width, image.size.height)
        let scale = min(1, maxDimension / max(sourceMaxDimension, 1))
        let outputImage: UIImage
        if scale < 1 {
            let targetSize = CGSize(
                width: max(1, (image.size.width * scale).rounded()),
                height: max(1, (image.size.height * scale).rounded())
            )
            let format = UIGraphicsImageRendererFormat()
            format.scale = 1
            format.opaque = true
            outputImage = UIGraphicsImageRenderer(size: targetSize, format: format).image { _ in
                image.draw(in: CGRect(origin: .zero, size: targetSize))
            }
        } else {
            outputImage = image
        }

        guard let data = outputImage.jpegData(compressionQuality: quality) else {
            throw APIError.invalidImage
        }
        return data
    }

    private func makeRequest(path: String, method: String) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: AppConfig.apiBaseURL) else {
            throw APIError.invalidResponse
        }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 120
        request.setValue(InstallationID.value(), forHTTPHeaderField: "X-Installation-ID")
        let language = Locale.preferredLanguages.first?.lowercased().hasPrefix("en") == true
            ? "en"
            : "zh-Hans"
        request.setValue(language, forHTTPHeaderField: "Accept-Language")
        if let appAccessToken = AppConfig.appAccessToken {
            request.setValue(appAccessToken, forHTTPHeaderField: "X-App-Token")
        }
        return request
    }

    private func send<T: Decodable>(_ request: URLRequest, as type: T.Type) async throws -> T {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.network
        }
        guard let http = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard 200..<300 ~= http.statusCode else {
            let detail = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["detail"] as? String
            throw APIError.server(detail ?? "请求失败，请稍后再试。")
        }
        do {
            return try JSONDecoder.api.decode(T.self, from: data)
        } catch {
            throw APIError.invalidResponse
        }
    }
}

private extension Data {
    mutating func append(_ string: String) {
        append(Data(string.utf8))
    }

    mutating func appendField(name: String, value: String, boundary: String) {
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
        append(value)
        append("\r\n")
    }

    mutating func appendFile(
        _ data: Data,
        name: String,
        filename: String,
        mimeType: String,
        boundary: String
    ) {
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"\(name)\"; filename=\"\(filename)\"\r\n")
        append("Content-Type: \(mimeType)\r\n\r\n")
        append(data)
        append("\r\n")
    }
}
