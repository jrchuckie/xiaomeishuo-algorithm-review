import Photos
import SwiftData
import SwiftUI
import UIKit

struct EditResultView: View {
    @Environment(\.modelContext) private var modelContext

    let result: GenerationResultDTO
    let sourcePath: String
    let resultPath: String
    let plan: EditPlanDTO
    let version: Int

    @State private var sourceImage: UIImage?
    @State private var resultImage: UIImage?
    @State private var comparisonValue = 0.5
    @State private var feedback = ""
    @State private var nextResult: GenerationResultDTO?
    @State private var nextResultPath: String?
    @State private var isWorking = false
    @State private var statusMessage: String?
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text("RESULT · V\(version)")
                        .font(.caption.weight(.semibold))
                        .tracking(1.6)
                        .foregroundStyle(AppTheme.wine)
                    Text("对比后，再决定")
                        .font(.system(size: 34, weight: .bold, design: .rounded))

                    if let sourceImage, let resultImage {
                        BeforeAfterComparison(
                            before: sourceImage,
                            after: resultImage,
                            value: $comparisonValue
                        )
                    }

                    Text(result.message)
                        .foregroundStyle(AppTheme.muted)
                        .card()

                    VStack(alignment: .leading, spacing: 10) {
                        Text("本轮质检").font(.headline)
                        ForEach(result.qualityNotes, id: \.self) { note in
                            Label(note, systemImage: "checkmark.circle.fill")
                                .foregroundStyle(AppTheme.wine)
                        }
                    }
                    .card()

                    VStack(alignment: .leading, spacing: 12) {
                        Text("哪里还不满意？")
                            .font(.headline)
                        Text("告诉小美下一版具体怎么调。只修改你指出的问题，其他部位继续锁定。")
                            .font(.footnote)
                            .foregroundStyle(AppTheme.muted)
                        TextField(
                            "例如：头脸再缩小一点；下颌线更清楚，但眼睛和鼻子完全不要动",
                            text: $feedback,
                            axis: .vertical
                        )
                        .lineLimit(4...8)
                        .padding(14)
                        .background(AppTheme.paper)
                        .clipShape(RoundedRectangle(cornerRadius: 14))

                        Button {
                            Task { await createNextVersion() }
                        } label: {
                            if isWorking {
                                ProgressView().tint(.white)
                            } else {
                                Text("按反馈生成 V\(version + 1)")
                            }
                        }
                        .buttonStyle(PrimaryButtonStyle())
                        .disabled(
                            feedback.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                || isWorking
                        )
                    }
                    .card()

                    Button {
                        Task { await saveToPhotos() }
                    } label: {
                        Label("满意，保存到相册", systemImage: "square.and.arrow.down.fill")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(resultImage == nil || isWorking)

                    if let statusMessage {
                        Text(statusMessage)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(AppTheme.wine)
                            .frame(maxWidth: .infinity, alignment: .center)
                    }
                    if let errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }
                }
                .padding(24)
            }
        }
        .navigationTitle("修图结果")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(item: $nextResult) { result in
            EditResultView(
                result: result,
                sourcePath: sourcePath,
                resultPath: nextResultPath ?? resultPath,
                plan: plan,
                version: version + 1
            )
        }
        .task { await loadImages() }
    }

    @MainActor
    private func loadImages() async {
        if
            let sourceURL = try? await LocalImageStore.shared.url(for: sourcePath),
            let data = try? Data(contentsOf: sourceURL)
        {
            sourceImage = UIImage(data: data)
        }
        if
            let resultURL = try? await LocalImageStore.shared.url(for: resultPath),
            let data = try? Data(contentsOf: resultURL)
        {
            resultImage = UIImage(data: data)
        }
    }

    @MainActor
    private func createNextVersion() async {
        isWorking = true
        errorMessage = nil
        statusMessage = nil
        defer { isWorking = false }
        do {
            let sourceURL = try await LocalImageStore.shared.url(for: sourcePath)
            let previousURL = try await LocalImageStore.shared.url(for: resultPath)
            let generated = try await APIClient.shared.generate(
                sourceURL: sourceURL,
                plan: plan,
                previousResultURL: previousURL,
                feedback: feedback
            )
            let savedPath: String
            if
                let encoded = generated.resultImageBase64,
                let data = Data(base64Encoded: encoded)
            {
                let fileExtension = generated.resultMimeType == "image/jpeg" ? "jpg" : "png"
                savedPath = try await LocalImageStore.shared.save(
                    data,
                    in: .editResults,
                    fileExtension: fileExtension
                )
            } else {
                savedPath = try await LocalImageStore.shared.copy(
                    relativePath: resultPath,
                    to: .editResults
                )
            }
            if let currentVersion = try findLocalVersion() {
                currentVersion.userFeedback = feedback
                currentVersion.liked = false
                modelContext.insert(
                    try LocalEditVersion(
                        sessionID: currentVersion.sessionID,
                        version: version + 1,
                        plan: plan,
                        resultImagePath: savedPath
                    )
                )
                try modelContext.save()
            }
            nextResultPath = savedPath
            nextResult = generated
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func saveToPhotos() async {
        guard resultImage != nil else { return }
        isWorking = true
        errorMessage = nil
        statusMessage = nil
        defer { isWorking = false }

        let authorization = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        guard authorization == .authorized || authorization == .limited else {
            errorMessage = "没有相册保存权限。请在系统设置中允许“小美说”添加照片。"
            return
        }
        do {
            let resultURL = try await LocalImageStore.shared.url(for: resultPath)
            try await PhotoLibrarySaver.saveImage(at: resultURL)
            if let currentVersion = try findLocalVersion() {
                currentVersion.liked = true
                try modelContext.save()
            }
            statusMessage = "已保存到系统相册"
        } catch {
            errorMessage = "保存失败，请稍后再试。"
        }
    }

    @MainActor
    private func findLocalVersion() throws -> LocalEditVersion? {
        let path = resultPath
        let descriptor = FetchDescriptor<LocalEditVersion>(
            predicate: #Predicate { $0.resultImagePath == path }
        )
        return try modelContext.fetch(descriptor).first
    }
}

private enum PhotoLibrarySaver {
    nonisolated static func saveImage(at fileURL: URL) async throws {
        try await PHPhotoLibrary.shared().performChanges {
            PHAssetChangeRequest.creationRequestForAssetFromImage(atFileURL: fileURL)
        }
    }
}
