import SwiftData
import SwiftUI

struct EditPlanView: View {
    @Environment(\.modelContext) private var modelContext

    let profile: AestheticProfileDTO
    @State private var plan: EditPlanDTO
    let sourcePath: String

    @State private var result: GenerationResultDTO?
    @State private var resultPath: String?
    @State private var isWorking = false
    @State private var errorMessage: String?
    @State private var editingChangeID: String?
    @State private var isAddingChange = false

    init(profile: AestheticProfileDTO, plan: EditPlanDTO, sourcePath: String) {
        self.profile = profile
        self._plan = State(initialValue: plan)
        self.sourcePath = sourcePath
    }

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text("STEP 3 · 修图方案")
                        .font(.caption.weight(.semibold))
                        .tracking(1.6)
                        .foregroundStyle(AppTheme.wine)
                    Text(plan.headline)
                        .font(.system(size: 32, weight: .bold, design: .rounded))
                    Text(plan.summary)
                        .foregroundStyle(AppTheme.muted)

                    ForEach($plan.changes) { $change in
                        VStack(alignment: .leading, spacing: 14) {
                            Toggle(isOn: $change.enabled) {
                                VStack(alignment: .leading, spacing: 7) {
                                    Text(change.area)
                                        .font(.caption.weight(.bold))
                                        .foregroundStyle(AppTheme.wine)
                                    Text(change.title)
                                        .font(.headline)
                                    Text(change.rationale)
                                        .font(.footnote)
                                        .foregroundStyle(AppTheme.muted)
                                }
                            }
                            .tint(AppTheme.wine)

                            Button {
                                editingChangeID = change.id
                            } label: {
                                Label("修改这一项", systemImage: "slider.horizontal.3")
                                    .font(.subheadline.weight(.semibold))
                            }
                            .foregroundStyle(AppTheme.wine)
                        }
                        .card()
                    }

                    Button {
                        isAddingChange = true
                    } label: {
                        Label("添加方案里没有的部位", systemImage: "plus.circle.fill")
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(AppTheme.blush)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                    }
                    .font(.headline)
                    .foregroundStyle(AppTheme.wine)

                    VStack(alignment: .leading, spacing: 8) {
                        Text("其他部位保持不变").font(.headline)
                        Text(plan.lockedRegions.joined(separator: " · "))
                            .font(.footnote)
                            .foregroundStyle(AppTheme.muted)
                    }
                    .card()

                    if let errorMessage {
                        Text(errorMessage).foregroundStyle(.red).font(.footnote)
                    }

                    Button {
                        Task { await generate() }
                    } label: {
                        isWorking ? AnyView(ProgressView().tint(.white)) : AnyView(Text("开始生成"))
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(!plan.changes.contains(where: \.enabled) || isWorking)
                }
                .padding(24)
            }
        }
        .sheet(isPresented: isEditingChange) {
            if
                let editingChangeID,
                let index = plan.changes.firstIndex(where: { $0.id == editingChangeID })
            {
                ChangeEditorSheet(
                    title: "修改调整要求",
                    confirmationTitle: "完成",
                    change: $plan.changes[index],
                    canDelete: true,
                    onDone: {},
                    onDelete: {
                        plan.changes.removeAll { $0.id == editingChangeID }
                        self.editingChangeID = nil
                    }
                )
            }
        }
        .sheet(isPresented: $isAddingChange) {
            NewChangeSheet { newChange in
                plan.changes.append(newChange)
                plan.lockedRegions.removeAll {
                    $0.localizedCaseInsensitiveContains(newChange.area)
                        || newChange.area.localizedCaseInsensitiveContains($0)
                }
            }
        }
        .navigationDestination(item: $result) { result in
            EditResultView(
                result: result,
                sourcePath: sourcePath,
                resultPath: resultPath ?? sourcePath,
                plan: plan,
                version: 1
            )
        }
    }

    private var isEditingChange: Binding<Bool> {
        Binding {
            editingChangeID != nil
        } set: { isPresented in
            if !isPresented {
                editingChangeID = nil
            }
        }
    }

    @MainActor
    private func generate() async {
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            let sourceURL = try await LocalImageStore.shared.url(for: sourcePath)
            let generated = try await APIClient.shared.generate(sourceURL: sourceURL, plan: plan)
            let session = LocalEditSession(profileID: UUID(), sourceImagePath: sourcePath)
            let savedResultPath: String
            if
                let encoded = generated.resultImageBase64,
                let imageData = Data(base64Encoded: encoded)
            {
                let fileExtension = generated.resultMimeType == "image/jpeg" ? "jpg" : "png"
                savedResultPath = try await LocalImageStore.shared.save(
                    imageData,
                    in: .editResults,
                    fileExtension: fileExtension
                )
            } else {
                savedResultPath = try await LocalImageStore.shared.copy(
                    relativePath: sourcePath,
                    to: .editResults
                )
            }
            modelContext.insert(session)
            modelContext.insert(
                try LocalEditVersion(
                    sessionID: session.id,
                    version: 1,
                    plan: plan,
                    resultImagePath: savedResultPath
                )
            )
            session.status = "completed"
            session.updatedAt = .now
            try modelContext.save()
            resultPath = savedResultPath
            result = generated
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

private struct ChangeEditorSheet: View {
    @Environment(\.dismiss) private var dismiss

    let title: LocalizedStringKey
    let confirmationTitle: LocalizedStringKey
    @Binding var change: EditChangeDTO
    let canDelete: Bool
    let onDone: () -> Void
    let onDelete: () -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("调整部位") {
                    TextField("例如：下颌线", text: $change.area)
                }
                Section("你希望怎么改") {
                    TextField("一句话目标", text: $change.title)
                    TextField(
                        "把你的要求写具体，比如“头脸比例缩小约一档，但不要削成 V 脸”",
                        text: $change.instruction,
                        axis: .vertical
                    )
                    .lineLimit(4...8)
                }
                if canDelete {
                    Section {
                        Button("删除这一项", role: .destructive) {
                            onDelete()
                            dismiss()
                        }
                    }
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(confirmationTitle) {
                        onDone()
                        dismiss()
                    }
                        .disabled(
                            change.area.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                || change.instruction.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                        )
                }
            }
        }
    }
}

private struct NewChangeSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var change = EditChangeDTO(
        id: UUID().uuidString,
        area: "",
        title: "",
        rationale: String(localized: "这是你在 AI 初稿之外主动添加的调整方向。"),
        instruction: "",
        enabled: true
    )

    let onSave: (EditChangeDTO) -> Void

    var body: some View {
        ChangeEditorSheet(
            title: "新增调整部位",
            confirmationTitle: "加入",
            change: $change,
            canDelete: false,
            onDone: {
                if change.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    change.title = String(
                        format: String(localized: "按我的要求调整%@"),
                        change.area
                    )
                }
                onSave(change)
            },
            onDelete: {}
        )
    }
}
