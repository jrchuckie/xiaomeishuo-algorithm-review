import SwiftData
import SwiftUI

struct MedicalPlanView: View {
    @Environment(\.modelContext) private var modelContext

    let profile: LocalAestheticProfile
    @State private var plan: MedicalPlanDTO
    let frontPath: String
    let sidePath: String?
    let intensity: MedicalIntensity

    @State private var result: GenerationResultDTO?
    @State private var resultPath: String?
    @State private var isWorking = false
    @State private var errorMessage: String?

    init(
        profile: LocalAestheticProfile,
        initialPlan: MedicalPlanDTO,
        frontPath: String,
        sidePath: String?,
        intensity: MedicalIntensity
    ) {
        self.profile = profile
        self._plan = State(initialValue: initialPlan)
        self.frontPath = frontPath
        self.sidePath = sidePath
        self.intensity = intensity
    }

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.lg) {
                    SilkHeader(
                        title: "目标方案地图",
                        subtitle: "先判断，再确认"
                    )

                    VStack(alignment: .leading, spacing: 8) {
                        Text("AESTHETIC TARGET · NOT A PRESCRIPTION")
                            .font(.caption.weight(.semibold))
                            .tracking(1.1)
                            .foregroundStyle(AppTheme.wine)
                        Text(plan.headline)
                            .font(.title2.bold())
                        Text(plan.summary)
                            .foregroundStyle(AppTheme.muted)
                    }
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    VStack(alignment: .leading, spacing: 6) {
                        Text("本次读取的审美方向")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.wine)
                        Text(plan.confirmedDirection)
                            .font(.title3.bold())
                        if let dto = profile.dto {
                            Text(dto.secondaryDirection)
                                .font(.subheadline)
                                .foregroundStyle(AppTheme.muted)
                        }
                    }
                    .padding(AppTheme.Spacing.md)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.blush)
                    .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.md))
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    ForEach($plan.candidates) { $candidate in
                        VStack(alignment: .leading, spacing: AppTheme.Spacing.sm) {
                            Toggle(isOn: $candidate.enabled) {
                                HStack(alignment: .top, spacing: AppTheme.Spacing.sm) {
                                    Text(
                                        String(
                                            format: "%02d",
                                            (plan.candidates.firstIndex(where: { $0.id == candidate.id }) ?? 0) + 1
                                        )
                                    )
                                    .font(.caption.bold())
                                    .foregroundStyle(AppTheme.wine)
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(candidate.area)
                                            .font(.headline)
                                        Text(candidate.goal)
                                            .font(.subheadline)
                                            .foregroundStyle(AppTheme.muted)
                                    }
                                }
                            }
                            .tint(AppTheme.wine)

                            Divider()

                            planRow("为什么", candidate.rationale)
                            planRow("本人证据", candidate.evidence)
                            planRow("面诊路径", candidate.methodCategory)
                            planRow("材料类别", candidate.materialCategory)
                            planRow("讨论范围", candidate.discussionRange)
                        }
                        .card()
                        .padding(.horizontal, AppTheme.Spacing.xl)
                    }

                    VStack(alignment: .leading, spacing: AppTheme.Spacing.sm) {
                        Label("明确保留", systemImage: "shield.checkered")
                            .font(.headline)
                            .foregroundStyle(AppTheme.wine)
                        ForEach(plan.preserve, id: \.self) { item in
                            Text("• \(item)")
                                .font(.subheadline)
                        }
                        Text("锁定：\(plan.lockedRegions.joined(separator: " · "))")
                            .font(.caption)
                            .foregroundStyle(AppTheme.muted)
                    }
                    .card()
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    if let errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                            .padding(.horizontal, AppTheme.Spacing.xl)
                    }

                    Button {
                        Task { await generate() }
                    } label: {
                        if isWorking {
                            ProgressView().tint(.white)
                        } else {
                            Text("生成完整目标效果")
                        }
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(!plan.candidates.contains(where: { $0.enabled }) || isWorking)
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    Text(plan.safetyDisclosure)
                        .font(.caption)
                        .foregroundStyle(AppTheme.tertiary)
                        .padding(.horizontal, AppTheme.Spacing.xl)
                        .padding(.bottom, AppTheme.Spacing.xl)
                }
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(item: $result) { generated in
            MedicalResultView(
                profile: profile,
                result: generated,
                sourcePath: frontPath,
                resultPath: resultPath ?? frontPath,
                plan: plan,
                intensity: intensity,
                version: 1
            )
        }
    }

    private func planRow(_ label: LocalizedStringKey, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label)
                .font(.caption.weight(.semibold))
                .foregroundStyle(AppTheme.wine)
            Text(value)
                .font(.footnote)
                .foregroundStyle(AppTheme.muted)
        }
    }

    @MainActor
    private func generate() async {
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            let sourceURL = try await LocalImageStore.shared.url(for: frontPath)
            let generated = try await APIClient.shared.generateMedical(
                sourceURL: sourceURL,
                plan: plan,
                intensity: intensity
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
                    relativePath: frontPath,
                    to: .medicalResults
                )
            }
            let descriptor = FetchDescriptor<LocalMedicalSession>(
                predicate: #Predicate { $0.frontImagePath == frontPath }
            )
            if let session = try modelContext.fetch(descriptor).last {
                session.planJSON = try JSONEncoder.api.encode(plan)
                session.resultImagePath = path
                session.updatedAt = .now
                try modelContext.save()
            }
            resultPath = path
            result = generated
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
