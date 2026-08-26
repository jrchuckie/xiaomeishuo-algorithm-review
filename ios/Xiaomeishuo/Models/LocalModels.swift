import Foundation
import SwiftData

@Model
final class LocalAestheticProfile {
    @Attribute(.unique) var id: UUID
    var remoteID: String
    var version: Int
    var primaryDirection: String
    var profileJSON: Data
    var sourceCount: Int
    var promptVersion: String
    var createdAt: Date
    var updatedAt: Date

    init(dto: AestheticProfileDTO, version: Int = 1) throws {
        id = UUID()
        remoteID = dto.id
        self.version = version
        primaryDirection = dto.primaryDirection
        profileJSON = try JSONEncoder.api.encode(dto)
        sourceCount = dto.sourceCount
        promptVersion = dto.promptVersion
        createdAt = .now
        updatedAt = .now
    }

    var dto: AestheticProfileDTO? {
        try? JSONDecoder.api.decode(AestheticProfileDTO.self, from: profileJSON)
    }
}

@Model
final class LocalReference {
    @Attribute(.unique) var id: UUID
    var sourceType: String
    var sourceURL: String?
    var localImagePath: String
    var included: Bool
    var preferenceWeight: Int
    var createdAt: Date

    init(sourceType: String, sourceURL: String? = nil, localImagePath: String) {
        id = UUID()
        self.sourceType = sourceType
        self.sourceURL = sourceURL
        self.localImagePath = localImagePath
        included = true
        preferenceWeight = 0
        createdAt = .now
    }
}

@Model
final class LocalEditSession {
    @Attribute(.unique) var id: UUID
    var profileID: UUID
    var sourceImagePath: String
    var status: String
    var createdAt: Date
    var updatedAt: Date

    init(profileID: UUID, sourceImagePath: String) {
        id = UUID()
        self.profileID = profileID
        self.sourceImagePath = sourceImagePath
        status = "draft"
        createdAt = .now
        updatedAt = .now
    }
}

@Model
final class LocalEditVersion {
    @Attribute(.unique) var id: UUID
    var sessionID: UUID
    var version: Int
    var planJSON: Data
    var userFeedback: String
    var resultImagePath: String
    var liked: Bool?
    var createdAt: Date

    init(sessionID: UUID, version: Int, plan: EditPlanDTO, resultImagePath: String) throws {
        id = UUID()
        self.sessionID = sessionID
        self.version = version
        planJSON = try JSONEncoder.api.encode(plan)
        userFeedback = ""
        self.resultImagePath = resultImagePath
        liked = nil
        createdAt = .now
    }

    var plan: EditPlanDTO? {
        try? JSONDecoder.api.decode(EditPlanDTO.self, from: planJSON)
    }

    var calibrationSignal: String? {
        let trimmedFeedback = userFeedback.trimmingCharacters(in: .whitespacesAndNewlines)
        if liked == true, let plan {
            let acceptedAreas = plan.changes
                .filter(\.enabled)
                .map(\.area)
                .joined(separator: "、")
            if !acceptedAreas.isEmpty {
                return "满意并保存；认可的调整方向：\(acceptedAreas)"
            }
        }
        if !trimmedFeedback.isEmpty {
            return liked == false
                ? "不满意并要求纠正：\(trimmedFeedback)"
                : "用户校准反馈：\(trimmedFeedback)"
        }
        return nil
    }
}

@Model
final class LocalMedicalSession {
    @Attribute(.unique) var id: UUID
    var profileID: UUID
    var frontImagePath: String
    var sideImagePath: String?
    var planJSON: Data
    var resultImagePath: String?
    var intensity: String
    var userFeedback: String
    var approved: Bool
    var createdAt: Date
    var updatedAt: Date

    init(
        profileID: UUID,
        frontImagePath: String,
        sideImagePath: String?,
        plan: MedicalPlanDTO,
        intensity: MedicalIntensity
    ) throws {
        id = UUID()
        self.profileID = profileID
        self.frontImagePath = frontImagePath
        self.sideImagePath = sideImagePath
        planJSON = try JSONEncoder.api.encode(plan)
        resultImagePath = nil
        self.intensity = intensity.rawValue
        userFeedback = ""
        approved = false
        createdAt = .now
        updatedAt = .now
    }

    var plan: MedicalPlanDTO? {
        try? JSONDecoder.api.decode(MedicalPlanDTO.self, from: planJSON)
    }
}

extension JSONEncoder {
    static let api: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()
}

extension JSONDecoder {
    static let api: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()
}
