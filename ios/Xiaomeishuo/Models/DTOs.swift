import Foundation

struct EvidenceDTO: Codable, Hashable {
    let referenceIndexes: [Int]
    let note: String
}

struct AestheticInsightDTO: Codable, Identifiable, Hashable {
    var id: String { "\(region)-\(title)" }
    let region: String
    let title: String
    let summary: String
    let confidence: String
    let evidence: EvidenceDTO
}

struct AestheticProfileDTO: Codable, Identifiable, Hashable {
    let id: String
    let primaryDirection: String
    let secondaryDirection: String
    let antiTargets: [String]
    let insights: [AestheticInsightDTO]
    let sourceCount: Int
    let generatedBy: String
    let promptVersion: String
}

struct BoardPreviewRequestDTO: Codable {
    let url: String
}

struct BoardPreviewItemDTO: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let thumbnailUrl: String?
    let selected: Bool
}

struct BoardPreviewDTO: Codable {
    let title: String
    let sourceUrl: String
    let status: String
    let message: String
    let items: [BoardPreviewItemDTO]
}

struct EditChangeDTO: Codable, Identifiable, Hashable {
    var id: String
    var area: String
    var title: String
    var rationale: String
    var instruction: String
    var enabled: Bool
}

struct EditPlanDTO: Codable, Identifiable, Hashable {
    let id: String
    var headline: String
    var summary: String
    var changes: [EditChangeDTO]
    var lockedRegions: [String]
    let promptVersion: String
    var intensity: String? = nil
}

struct QualityVerdictDTO: Codable, Hashable {
    let identityScore: Int
    let framingScore: Int
    let headBoundaryScore: Int
    let targetChangeScore: Int
    let widthSafetyScore: Int
    let cheekSafetyScore: Int
    let lockedRegionScore: Int
    let hardFailures: [String]
    let summary: String
    let eligible: Bool
    let retryInstruction: String
}

struct GenerationResultDTO: Codable, Identifiable, Hashable {
    let id: String
    let status: String
    let resultMode: String
    let message: String
    let qualityNotes: [String]
    let resultImageBase64: String?
    let resultMimeType: String?
    var qualityVerdict: QualityVerdictDTO? = nil
    var candidateCount: Int? = nil
    var correctionRounds: Int? = nil
    var semanticJudgeCount: Int? = nil
    var deterministicRejectCount: Int? = nil
    var stageTimingsMs: [String: Int]? = nil
    var generationProvider: String? = nil
}

enum APIIntensity: String, Hashable {
    case natural
    case visible
}

enum MedicalIntensity: String, Codable, CaseIterable, Hashable, Identifiable {
    case conservative
    case balanced
    case visible

    var id: String { rawValue }

    var label: String {
        switch self {
        case .conservative: String(localized: "保守验证")
        case .balanced: String(localized: "充分改善")
        case .visible: String(localized: "明显目标")
        }
    }
}

struct MedicalCandidateDTO: Codable, Identifiable, Hashable {
    var id: String
    var area: String
    var goal: String
    var priority: String
    var methodCategory: String
    var materialCategory: String
    var discussionRange: String
    var rationale: String
    var evidence: String
    var consultationQuestions: [String]
    var enabled: Bool
}

struct MedicalPlanDTO: Codable, Identifiable, Hashable {
    let id: String
    var headline: String
    var summary: String
    var confirmedDirection: String
    var preserve: [String]
    var candidates: [MedicalCandidateDTO]
    var lockedRegions: [String]
    var consultationQuestions: [String]
    var safetyDisclosure: String
    let promptVersion: String
}
