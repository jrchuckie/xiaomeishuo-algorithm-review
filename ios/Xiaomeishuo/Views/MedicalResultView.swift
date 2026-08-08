import Photos
import SwiftData
import SwiftUI
import UIKit

struct MedicalResultView: View {
    @Environment(\.modelContext) private var modelContext

    let profile: LocalAestheticProfile
    let result: GenerationResultDTO
    let sourcePath: String
    let resultPath: String
    let plan: MedicalPlanDTO
    let intensity: MedicalIntensity
    let version: Int

    @State private var sourceImage: UIImage?
    @State private var resultImage: UIImage?
    @State private var comparisonValue = 0.5
    @State private var feedback = ""
    @State private var nextResult: GenerationResultDTO?
    @State private var nextPath: String?
    @State private var showPlan = false
    @State private var isWorking = false
    @State private var statusMessage: String?
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.lg) {
                    SilkHeader(
                        title: "确认效果",
                        subtitle: "先看目标，再展开唯一方案"
                    )

                    VStack(alignment: .leading, spacing: 6) {
                        Text("TARGET EFFECT · V\(version)")
                            .font(.caption.weight(.semibold))
                            .tracking(1.1)
                            .foregroundStyle(AppTheme.wine)
                        Text("这是不是你想讨论的方向？")
                            .font(.title2.bold())
                    }
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    if let sourceImage, let resultImage {
                        BeforeAfterComparison(
                            before: sourceImage,
                            after: resultImage,
                            value: $comparisonValue
                        )
                        .padding(.horizontal, AppTheme.Spacing.xl)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Label(
                            result.resultMode == "safe_original" ? "本轮安全保留原图" : "审美目标已生成",
                            systemImage: result.resultMode == "safe_original"
                                ? "shield.checkered"
                                : "sparkles"
                        )
                        .font(.headline)
                        .foregroundStyle(AppTheme.wine)
                        Text(result.message)
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.muted)
                        ForEach(result.qualityNotes, id: \.self) { note in
                            Text("• \(note)")
                                .font(.caption)
                                .foregroundStyle(AppTheme.tertiary)
                        }
                    }
                    .card()
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    VStack(alignment: .leading, spacing: AppTheme.Spacing.sm) {
                        Text("哪里还不满意？")
                            .font(.headline)
                        Text("只调整你指出的问题，眼睛和其他未选部位继续锁定。")
                            .font(.footnote)
                            .foregroundStyle(AppTheme.muted)
                        TextField(
                            "例如：下巴前移更明显；下颌线再清楚，但眼睛、鼻子完全不要动",
                            text: $feedback,
                            axis: .vertical
                        )
                        .lineLimit(3...7)
                        .padding(12)
                        .background(AppTheme.subtle)
                        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.sm))

                        Button {
                            Task { await createNextVersion() }
                        } label: {
                            if isWorking {
                                ProgressView().tint(.white)
                            } else {
                                Text("按反馈生成 V\(version + 1)")
                            }
                        }
                        .buttonStyle(SecondaryButtonStyle())
                        .disabled(feedback.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isWorking)
                    }
                    .card()
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    Button {
                        showPlan = true
                    } label: {
                        Text("满意，查看唯一方案")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(result.resultMode == "safe_original")
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    Button {
                        Task { await saveToPhotos() }
                    } label: {
                        Label("保存目标效果", systemImage: "square.and.arrow.down")
                    }
                    .buttonStyle(SecondaryButtonStyle())
                    .disabled(resultImage == nil || isWorking)
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    if let statusMessage {
                        Text(statusMessage)
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(AppTheme.wine)
                            .frame(maxWidth: .infinity)
                    }
                    if let errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                            .padding(.horizontal, AppTheme.Spacing.xl)
                    }

                    Text("目标图用于表达审美方向，不代表一次治疗或特定项目可以达到。")
                        .font(.caption)
                        .foregroundStyle(AppTheme.tertiary)
                        .padding(.horizontal, AppTheme.Spacing.xl)
                        .padding(.bottom, AppTheme.Spacing.xl)
                }
            }
        }
        .navigationDestination(isPresented: $showPlan) {
            MedicalReportView(profile: profile, plan: plan, resultPath: resultPath)
        }
        .navigationDestination(item: $nextResult) { generated in
            MedicalResultView(
                profile: profile,
                result: generated,
                sourcePath: sourcePath,
                resultPath: nextPath ?? resultPath,
                plan: plan,
                intensity: intensity,
                version: version + 1
            )
        }
        .task { await loadImages() }
    }

    @MainActor
    private func loadImages() async {
        if
            let url = try? await LocalImageStore.shared.url(for: sourcePath),
            let data = try? Data(contentsOf: url)
        {
            sourceImage = UIImage(data: data)
        }
        if
            let url = try? await LocalImageStore.shared.url(for: resultPath),
            let data = try? Data(contentsOf: url)
        {
            resultImage = UIImage(data: data)
        }
    }

    @MainActor
    private func createNextVersion() async {
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            let sourceURL = try await LocalImageStore.shared.url(for: sourcePath)
            let previousURL = try await LocalImageStore.shared.url(for: resultPath)
            let generated = try await APIClient.shared.generateMedical(
                sourceURL: sourceURL,
                plan: plan,
                intensity: intensity,
                previousResultURL: previousURL,
                feedback: feedback
            )
            let path: String
            if
                let encoded = generated.resultImageBase64,
                let data = Data(base64Encoded: encoded)
            {
                path = try await LocalImageStore.shared.save(
                    data,
                    in: .medicalResults,
                    fileExtension: generated.resultMimeType == "image/jpeg" ? "jpg" : "png"
                )
            } else {
                path = try await LocalImageStore.shared.copy(
                    relativePath: resultPath,
                    to: .medicalResults
                )
            }
            updateLocalSession(resultPath: path, feedback: feedback, approved: false)
            nextPath = path
            nextResult = generated
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func saveToPhotos() async {
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        let authorization = await PHPhotoLibrary.requestAuthorization(for: .addOnly)
        guard authorization == .authorized || authorization == .limited else {
            errorMessage = String(localized: "没有相册保存权限。请在系统设置中允许“小美说”添加照片。")
            return
        }
        do {
            let url = try await LocalImageStore.shared.url(for: resultPath)
            try await PHPhotoLibrary.shared().performChanges {
                PHAssetChangeRequest.creationRequestForAssetFromImage(atFileURL: url)
            }
            updateLocalSession(resultPath: resultPath, feedback: feedback, approved: true)
            statusMessage = String(localized: "已保存到系统相册")
        } catch {
            errorMessage = String(localized: "保存失败，请稍后再试。")
        }
    }

    @MainActor
    private func updateLocalSession(resultPath: String, feedback: String, approved: Bool) {
        let source = sourcePath
        let descriptor = FetchDescriptor<LocalMedicalSession>(
            predicate: #Predicate { $0.frontImagePath == source }
        )
        guard let session = try? modelContext.fetch(descriptor).last else { return }
        session.resultImagePath = resultPath
        session.userFeedback = feedback
        session.approved = approved
        session.updatedAt = .now
        try? modelContext.save()
    }
}
