import PhotosUI
import SwiftData
import SwiftUI

struct MedicalStartView: View {
    @Environment(\.modelContext) private var modelContext
    @Query(sort: \LocalMedicalSession.updatedAt, order: .reverse)
    private var medicalSessions: [LocalMedicalSession]

    let profile: LocalAestheticProfile

    @State private var frontPicker: PhotosPickerItem?
    @State private var sidePicker: PhotosPickerItem?
    @State private var frontPath: String?
    @State private var sidePath: String?
    @State private var selectedDirections = Set(["下颌线", "下巴"])
    @State private var intensity: MedicalIntensity = .balanced
    @State private var budget = "1–3万"
    @State private var downtime = "可接受 1–3 天"
    @State private var mustPreserve = "眼睛大小、鼻部辨识度、本人感"
    @State private var currentConcern = ""
    @State private var previousTreatments = ""
    @State private var riskPreference = "先可逆、后不可逆"
    @State private var consentedToProcessing = false
    @State private var plan: MedicalPlanDTO?
    @State private var isWorking = false
    @State private var errorMessage: String?
    @State private var validationNotice: String?

    private let directions = [
        "下颌线", "下巴", "面中", "太阳穴", "鼻部", "眼睛", "眉形", "嘴唇", "肤质",
    ]

    private var profileSessions: [LocalMedicalSession] {
        medicalSessions.filter { $0.profileID == profile.id }
    }

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.lg) {
                    SilkHeader(
                        title: "本人映射",
                        subtitle: "先看本人，再讨论目标"
                    )

                    VStack(alignment: .leading, spacing: 8) {
                        Text("STEP 1 · 真实面部")
                            .font(.caption.weight(.semibold))
                            .tracking(1.2)
                            .foregroundStyle(AppTheme.wine)
                        Text("上传正面照与一张 45°")
                            .font(.title2.bold())
                        Text("正面照必选；45° 用来核对下巴、下颌与面中衔接。原图保存在本机，只有你主动生成时才会临时发送给 AI。")
                            .font(.subheadline)
                            .foregroundStyle(AppTheme.muted)
                    }
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    HStack(spacing: AppTheme.Spacing.sm) {
                        photoPicker(
                            title: "正面照",
                            note: "必选",
                            hasPhoto: frontPath != nil,
                            selection: $frontPicker
                        )
                        photoPicker(
                            title: "左/右 45°",
                            note: "推荐",
                            hasPhoto: sidePath != nil,
                            selection: $sidePicker
                        )
                    }
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    VStack(alignment: .leading, spacing: AppTheme.Spacing.md) {
                        Text("STEP 2 · 目标方案地图")
                            .font(.caption.weight(.semibold))
                            .tracking(1.2)
                            .foregroundStyle(AppTheme.wine)
                        Text("只选择你真的想讨论的部位")
                            .font(.title3.bold())
                        Text("没有选择的部位会写入锁定清单。尤其眼睛未选择时，目标图绝不允许变大或改变眼型。")
                            .font(.footnote)
                            .foregroundStyle(AppTheme.muted)

                        LazyVGrid(
                            columns: [GridItem(.flexible()), GridItem(.flexible())],
                            spacing: AppTheme.Spacing.sm
                        ) {
                            ForEach(directions, id: \.self) { direction in
                                Button {
                                    if selectedDirections.contains(direction) {
                                        selectedDirections.remove(direction)
                                    } else {
                                        selectedDirections.insert(direction)
                                    }
                                } label: {
                                    HStack {
                                        Text(LocalizedStringKey(direction))
                                        Spacer()
                                        Image(
                                            systemName: selectedDirections.contains(direction)
                                                ? "checkmark.circle.fill"
                                                : "circle"
                                        )
                                    }
                                    .font(.subheadline.weight(.semibold))
                                    .foregroundStyle(
                                        selectedDirections.contains(direction)
                                            ? AppTheme.wine
                                            : AppTheme.muted
                                    )
                                    .padding(.horizontal, 14)
                                    .frame(minHeight: 44)
                                    .background(
                                        selectedDirections.contains(direction)
                                            ? AppTheme.blush
                                            : AppTheme.subtle
                                    )
                                    .clipShape(
                                        RoundedRectangle(
                                            cornerRadius: AppTheme.Radius.md,
                                            style: .continuous
                                        )
                                    )
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .card()
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    VStack(alignment: .leading, spacing: AppTheme.Spacing.md) {
                        Text("你希望目标变化多明显？")
                            .font(.headline)
                        Picker("目标变化强度", selection: $intensity) {
                            ForEach(MedicalIntensity.allCases) { value in
                                Text(value.label).tag(value)
                            }
                        }
                        .pickerStyle(.segmented)

                        Picker("预算边界", selection: $budget) {
                            Text("1 万以内").tag("1万以内")
                            Text("1–3 万").tag("1–3万")
                            Text("3–5 万").tag("3–5万")
                            Text("先看方向").tag("先看方向")
                        }

                        Picker("恢复期", selection: $downtime) {
                            Text("不接受恢复期").tag("不接受恢复期")
                            Text("可接受 1–3 天").tag("可接受 1–3 天")
                            Text("可接受 1–2 周").tag("可接受 1–2 周")
                        }

                        TextField("必须保留什么", text: $mustPreserve, axis: .vertical)
                            .lineLimit(2...4)
                            .padding(12)
                            .background(AppTheme.subtle)
                            .clipShape(
                                RoundedRectangle(
                                    cornerRadius: AppTheme.Radius.sm,
                                    style: .continuous
                                )
                            )

                        TextField("你现在最困扰的是什么？", text: $currentConcern, axis: .vertical)
                            .lineLimit(2...4)
                            .padding(12)
                            .background(AppTheme.subtle)
                            .clipShape(
                                RoundedRectangle(
                                    cornerRadius: AppTheme.Radius.sm,
                                    style: .continuous
                                )
                            )

                        TextField("曾做过哪些项目（可不填）", text: $previousTreatments, axis: .vertical)
                            .lineLimit(2...4)
                            .padding(12)
                            .background(AppTheme.subtle)
                            .clipShape(
                                RoundedRectangle(
                                    cornerRadius: AppTheme.Radius.sm,
                                    style: .continuous
                                )
                            )

                        Picker("决策偏好", selection: $riskPreference) {
                            Text("先可逆、后不可逆").tag("先可逆、后不可逆")
                            Text("优先非手术").tag("优先非手术")
                            Text("开放讨论不同路径").tag("开放讨论不同路径")
                        }
                    }
                    .card()
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    Toggle(isOn: $consentedToProcessing) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text("同意本次 AI 处理")
                                .font(.subheadline.weight(.semibold))
                            Text("仅在点击生成后发送所选照片；服务端不建立用户档案，也不把照片写入业务数据库。")
                                .font(.caption)
                                .foregroundStyle(AppTheme.muted)
                        }
                    }
                    .tint(AppTheme.wine)
                    .card()
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    if !profileSessions.isEmpty {
                        VStack(alignment: .leading, spacing: AppTheme.Spacing.sm) {
                            Text("本机最近方案")
                                .font(.headline)
                            ForEach(profileSessions.prefix(3)) { session in
                                if
                                    let plan = session.plan,
                                    let resultPath = session.resultImagePath
                                {
                                    NavigationLink {
                                        MedicalReportView(
                                            profile: profile,
                                            plan: plan,
                                            resultPath: resultPath
                                        )
                                    } label: {
                                        HStack {
                                            VStack(alignment: .leading, spacing: 3) {
                                                Text(plan.headline)
                                                    .font(.subheadline.weight(.semibold))
                                                    .lineLimit(1)
                                                Text(session.updatedAt, style: .date)
                                                    .font(.caption)
                                                    .foregroundStyle(AppTheme.muted)
                                            }
                                            Spacer()
                                            Image(systemName: "chevron.right")
                                                .foregroundStyle(AppTheme.tertiary)
                                        }
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                        }
                        .card()
                        .padding(.horizontal, AppTheme.Spacing.xl)
                    }

                    if let errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                            .padding(.horizontal, AppTheme.Spacing.xl)
                    }
                    if let validationNotice {
                        Label(validationNotice, systemImage: "info.circle")
                            .font(.footnote)
                            .foregroundStyle(AppTheme.wine)
                            .padding(.horizontal, AppTheme.Spacing.xl)
                    }

                    Button {
                        Task { await createPlan() }
                    } label: {
                        if isWorking {
                            ProgressView().tint(.white)
                        } else {
                            Text("生成我的目标方案")
                        }
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(
                        frontPath == nil
                            || selectedDirections.isEmpty
                            || !consentedToProcessing
                            || isWorking
                    )
                    .padding(.horizontal, AppTheme.Spacing.xl)

                    Text("这是审美决策支持，不是诊断或处方。")
                        .font(.caption)
                        .foregroundStyle(AppTheme.tertiary)
                        .frame(maxWidth: .infinity)
                        .padding(.bottom, AppTheme.Spacing.xl)
                }
            }
        }
        .navigationBarHidden(true)
        .navigationDestination(item: $plan) { plan in
            MedicalPlanView(
                profile: profile,
                initialPlan: plan,
                frontPath: frontPath ?? "",
                sidePath: sidePath,
                intensity: intensity
            )
        }
        .onChange(of: frontPicker) { _, item in
            guard let item else { return }
            Task { frontPath = await importPhoto(item) }
        }
        .onChange(of: sidePicker) { _, item in
            guard let item else { return }
            Task { sidePath = await importPhoto(item) }
        }
    }

    private func photoPicker(
        title: LocalizedStringKey,
        note: LocalizedStringKey,
        hasPhoto: Bool,
        selection: Binding<PhotosPickerItem?>
    ) -> some View {
        PhotosPicker(selection: selection, matching: .images) {
            VStack(spacing: 10) {
                Image(systemName: hasPhoto ? "checkmark.circle.fill" : "photo.badge.plus")
                    .font(.title2)
                Text(title)
                    .font(.headline)
                Text(note)
                    .font(.caption)
                    .foregroundStyle(AppTheme.tertiary)
            }
            .foregroundStyle(AppTheme.wine)
            .frame(maxWidth: .infinity)
            .frame(height: 136)
            .background(hasPhoto ? AppTheme.blush : AppTheme.surface)
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.lg))
            .overlay {
                RoundedRectangle(cornerRadius: AppTheme.Radius.lg)
                    .stroke(hasPhoto ? AppTheme.silk : AppTheme.border, lineWidth: hasPhoto ? 2 : 1)
            }
        }
    }

    @MainActor
    private func importPhoto(_ item: PhotosPickerItem) async -> String? {
        do {
            guard let data = try await item.loadTransferable(type: Data.self) else { return nil }
            return try await LocalImageStore.shared.save(data, in: .medicalSources)
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    @MainActor
    private func createPlan() async {
        guard
            let dto = profile.dto,
            let frontPath
        else { return }
        isWorking = true
        errorMessage = nil
        validationNotice = nil
        defer { isWorking = false }
        do {
            let frontURL = try await LocalImageStore.shared.url(for: frontPath)
            let sideURL: URL?
            if let sidePath {
                sideURL = try await LocalImageStore.shared.url(for: sidePath)
            } else {
                sideURL = nil
            }
            let validation: FacePhotoValidationResult
            if let sideURL {
                validation = try await FacePhotoValidator.validatePair(
                    front: frontURL,
                    angle45: sideURL
                )
            } else {
                validation = try await FacePhotoValidator.validate(at: frontURL, role: .front)
            }
            validationNotice = validation.noticeMessage
            let preferences = [
                "budget": budget,
                "downtime": downtime,
                "must_preserve": mustPreserve,
                "current_concern": currentConcern,
                "previous_treatments": previousTreatments,
                "decision_preference": riskPreference,
            ]
            let result = try await APIClient.shared.createMedicalPlan(
                frontURL: frontURL,
                sideURL: sideURL,
                profile: dto,
                preferences: preferences,
                selectedDirections: selectedDirections.sorted(),
                intensity: intensity
            )
            modelContext.insert(
                try LocalMedicalSession(
                    profileID: profile.id,
                    frontImagePath: frontPath,
                    sideImagePath: sidePath,
                    plan: result,
                    intensity: intensity
                )
            )
            try modelContext.save()
            plan = result
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
