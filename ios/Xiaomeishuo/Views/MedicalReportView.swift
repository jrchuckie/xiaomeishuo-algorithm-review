import SwiftUI
import UIKit

struct MedicalReportView: View {
    let profile: LocalAestheticProfile
    let plan: MedicalPlanDTO
    let resultPath: String

    @State private var resultImage: UIImage?
    @State private var showShare = false

    private var activeCandidates: [MedicalCandidateDTO] {
        plan.candidates.filter { $0.enabled && $0.priority != "avoid" }
    }

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.lg) {
                    SilkHeader(
                        title: "唯一方案",
                        subtitle: "只呈现与这张效果对应的方案"
                    )

                    VStack(alignment: .leading, spacing: 6) {
                        Text("ONE EFFECT · ONE PLAN")
                            .font(.caption.weight(.semibold))
                            .tracking(1.1)
                            .foregroundStyle(AppTheme.wine)
                        Text("把确认过的方向，变成沟通顺序")
                            .font(.title3.bold())
                    }
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    VStack(alignment: .leading, spacing: 5) {
                        Text("已确认效果")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(AppTheme.wine)
                        Text(plan.confirmedDirection)
                            .font(.title3.bold())
                        Text(activeCandidates.map(\.area).joined(separator: " · "))
                            .font(.caption)
                            .foregroundStyle(AppTheme.muted)
                    }
                    .padding(AppTheme.Spacing.md)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(AppTheme.blush)
                    .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.md))
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    VStack(spacing: 0) {
                        ForEach(Array(activeCandidates.enumerated()), id: \.element.id) { index, item in
                            HStack(alignment: .top, spacing: AppTheme.Spacing.sm) {
                                Text(String(format: "%02d", index + 1))
                                    .font(.caption.bold())
                                    .foregroundStyle(AppTheme.wine)
                                    .frame(width: 24, alignment: .leading)
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(priorityLabel(item.priority))
                                        .font(.caption.weight(.semibold))
                                        .foregroundStyle(AppTheme.wine)
                                    Text("\(item.area) · \(item.goal)")
                                        .font(.subheadline.weight(.semibold))
                                    Text(item.methodCategory)
                                        .font(.caption)
                                        .foregroundStyle(AppTheme.muted)
                                }
                                Spacer()
                            }
                            .padding(.vertical, AppTheme.Spacing.sm)
                            if index < activeCandidates.count - 1 {
                                Divider()
                            }
                        }
                    }
                    .card()
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    VStack(alignment: .leading, spacing: AppTheme.Spacing.sm) {
                        Label("面诊问题清单", systemImage: "list.clipboard")
                            .font(.headline)
                            .foregroundStyle(AppTheme.wine)
                        ForEach(plan.consultationQuestions, id: \.self) { question in
                            Text("• \(question)")
                                .font(.subheadline)
                        }
                    }
                    .card()
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    VStack(alignment: .leading, spacing: 8) {
                        Label("材料与用量边界", systemImage: "shield.checkered")
                            .font(.headline)
                        Text("方案只呈现材料类别与面诊讨论范围，不把照片当作个人处方。具体品牌、个人用量、针点和层次必须由合资格医生面诊决定。")
                            .font(.footnote)
                            .foregroundStyle(AppTheme.muted)
                        Text(plan.safetyDisclosure)
                            .font(.caption)
                            .foregroundStyle(AppTheme.tertiary)
                    }
                    .padding(AppTheme.Spacing.md)
                    .background(AppTheme.subtle)
                    .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.md))
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    Button {
                        showShare = true
                    } label: {
                        Label("导出面诊沟通卡", systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .padding(.horizontal, AppTheme.Spacing.xl)
                    .padding(.bottom, AppTheme.Spacing.xl)
                }
            }
        }
        .task { await loadResult() }
        .sheet(isPresented: $showShare) {
            if let image = renderConsultationCard() {
                ShareSheet(items: [image])
            }
        }
    }

    private func priorityLabel(_ priority: String) -> LocalizedStringKey {
        switch priority {
        case "now": "先讨论"
        case "later": "再评估"
        case "optional": "可选"
        default: "明确保留"
        }
    }

    @MainActor
    private func loadResult() async {
        if
            let url = try? await LocalImageStore.shared.url(for: resultPath),
            let data = try? Data(contentsOf: url)
        {
            resultImage = UIImage(data: data)
        }
    }

    @MainActor
    private func renderConsultationCard() -> UIImage? {
        let content = ConsultationCardContent(plan: plan, resultImage: resultImage)
            .frame(width: 390)
        let renderer = ImageRenderer(content: content)
        renderer.scale = 3
        return renderer.uiImage
    }
}

private struct ConsultationCardContent: View {
    let plan: MedicalPlanDTO
    let resultImage: UIImage?

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("小美说")
                .font(.title2.bold())
            Text("面诊沟通卡")
                .font(.largeTitle.bold())
            Text(plan.confirmedDirection)
                .font(.headline)
                .foregroundStyle(AppTheme.wine)
            if let resultImage {
                Image(uiImage: resultImage)
                    .resizable()
                    .scaledToFill()
                    .frame(height: 300)
                    .clipped()
                    .clipShape(RoundedRectangle(cornerRadius: 20))
            }
            ForEach(Array(plan.candidates.filter(\.enabled).prefix(4).enumerated()), id: \.element.id) { index, item in
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(index + 1). \(item.area) · \(item.goal)")
                        .font(.headline)
                    Text(item.methodCategory)
                        .font(.caption)
                        .foregroundStyle(AppTheme.muted)
                }
            }
            Text(plan.safetyDisclosure)
                .font(.caption2)
                .foregroundStyle(AppTheme.tertiary)
        }
        .padding(28)
        .background(AppTheme.paper)
        .foregroundStyle(AppTheme.ink)
    }
}

private struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
