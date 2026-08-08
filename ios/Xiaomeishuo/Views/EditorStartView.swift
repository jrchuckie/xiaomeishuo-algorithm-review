import PhotosUI
import SwiftData
import SwiftUI

struct EditorStartView: View {
    @Environment(\.modelContext) private var modelContext

    let profile: AestheticProfileDTO

    @State private var selectedPhoto: PhotosPickerItem?
    @State private var sourcePath: String?
    @State private var intensity: APIIntensity = .visible
    @State private var plan: EditPlanDTO?
    @State private var isWorking = false
    @State private var errorMessage: String?
    @State private var validationNotice: String?

    var body: some View {
        let hasSource = sourcePath != nil
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text("STEP 2 · 个性化修图")
                        .font(.caption.weight(.semibold))
                        .tracking(1.6)
                        .foregroundStyle(AppTheme.wine)
                    Text("上传一张照片，\n先确认修什么")
                        .font(.system(size: 34, weight: .bold, design: .rounded))

                    PhotosPicker(selection: $selectedPhoto, matching: .images) {
                        VStack(spacing: 12) {
                            Image(systemName: hasSource ? "checkmark.circle.fill" : "photo.badge.plus")
                                .font(.system(size: 34))
                            Text(
                                hasSource
                                    ? String(localized: "照片已保存到本机")
                                    : String(localized: "选择待修照片")
                            )
                                .font(.headline)
                        }
                        .foregroundStyle(AppTheme.wine)
                        .frame(maxWidth: .infinity)
                        .frame(height: 180)
                        .background(AppTheme.blush)
                        .clipShape(RoundedRectangle(cornerRadius: 24))
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        Text("变化强度").font(.headline)
                        Picker("变化强度", selection: $intensity) {
                            Text("自然优化").tag(APIIntensity.natural)
                            Text("明显改变").tag(APIIntensity.visible)
                        }
                        .pickerStyle(.segmented)
                        Text(
                            intensity == .visible
                                ? String(localized: "第一眼能看出比例和状态更好，但仍然是本人。")
                                : String(localized: "像状态很好的一天，变化更克制。")
                        )
                            .font(.footnote)
                            .foregroundStyle(AppTheme.muted)
                    }
                    .card()

                    if let errorMessage {
                        Text(errorMessage).foregroundStyle(.red).font(.footnote)
                    }
                    if let validationNotice {
                        Label(validationNotice, systemImage: "info.circle")
                            .foregroundStyle(AppTheme.wine)
                            .font(.footnote)
                    }

                    Button {
                        Task { await createPlan() }
                    } label: {
                        isWorking ? AnyView(ProgressView().tint(.white)) : AnyView(Text("生成修图方案"))
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(sourcePath == nil || isWorking)
                }
                .padding(24)
            }
        }
        .navigationDestination(item: $plan) { plan in
            EditPlanView(profile: profile, plan: plan, sourcePath: sourcePath ?? "")
        }
        .onChange(of: selectedPhoto) { _, item in
            guard let item else { return }
            Task { await importSource(item) }
        }
    }

    @MainActor
    private func importSource(_ item: PhotosPickerItem) async {
        do {
            guard let data = try await item.loadTransferable(type: Data.self) else { return }
            sourcePath = try await LocalImageStore.shared.save(data, in: .editSources)
            validationNotice = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func createPlan() async {
        guard let sourcePath else { return }
        isWorking = true
        errorMessage = nil
        validationNotice = nil
        defer { isWorking = false }
        do {
            let url = try await LocalImageStore.shared.url(for: sourcePath)
            let validation = try await FacePhotoValidator.validate(at: url)
            validationNotice = validation.noticeMessage
            plan = try await APIClient.shared.createEditPlan(
                sourceURL: url,
                profile: profile,
                intensity: intensity
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
