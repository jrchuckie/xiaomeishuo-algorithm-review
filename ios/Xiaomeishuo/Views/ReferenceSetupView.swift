import PhotosUI
import SwiftData
import SwiftUI

struct ReferenceSetupView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.dismiss) private var dismiss
    @Query(sort: \LocalEditVersion.createdAt, order: .reverse)
    private var editVersions: [LocalEditVersion]

    @State private var boardURL = ""
    @State private var boardMessage: String?
    @State private var boardItems: [BoardPreviewItemDTO] = []
    @State private var selectedBoardIDs = Set<String>()
    @State private var selectedItems: [PhotosPickerItem] = []
    @State private var localPaths: [String] = []
    @State private var isWorking = false
    @State private var errorMessage: String?
    @State private var generatedProfile: AestheticProfileDTO?

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text("STEP 1 · 理想样本")
                        .font(.caption.weight(.semibold))
                        .tracking(1.6)
                        .foregroundStyle(AppTheme.wine)

                    Text("让我先看懂，\n你真正喜欢什么")
                        .font(.system(size: 34, weight: .bold, design: .rounded))

                    boardCard
                    uploadCard

                    if let errorMessage {
                        Text(errorMessage)
                            .font(.footnote)
                            .foregroundStyle(.red)
                    }

                    Button {
                        Task { await createProfile() }
                    } label: {
                        if isWorking {
                            ProgressView().tint(.white)
                        } else {
                            Text(localPaths.count >= 3 ? "生成我的审美画像" : "还需要 \(3 - localPaths.count) 张参考图")
                        }
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    .disabled(localPaths.count < 3 || isWorking)
                }
                .padding(24)
            }
        }
        .navigationDestination(item: $generatedProfile) { profile in
            ProfileView(profile: profile, isNewProfile: true)
        }
        .onChange(of: selectedItems) { _, items in
            Task { await importPhotos(items) }
        }
    }

    private var boardCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("导入小红书收藏夹", systemImage: "link")
                .font(.headline)
            TextField("粘贴公开收藏夹分享链接", text: $boardURL)
                .textInputAutocapitalization(.never)
                .keyboardType(.URL)
                .padding(14)
                .background(AppTheme.paper)
                .clipShape(RoundedRectangle(cornerRadius: 14))
            Button("读取公开收藏夹") {
                Task { await previewBoard() }
            }
            .font(.subheadline.weight(.semibold))
            .disabled(boardURL.isEmpty || isWorking)
            if let boardMessage {
                Text(boardMessage)
                    .font(.footnote)
                    .foregroundStyle(AppTheme.muted)
            }
            if !boardItems.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    LazyHStack(spacing: 10) {
                        ForEach(boardItems) { item in
                            Button {
                                if selectedBoardIDs.contains(item.id) {
                                    selectedBoardIDs.remove(item.id)
                                } else {
                                    selectedBoardIDs.insert(item.id)
                                }
                            } label: {
                                VStack(alignment: .leading, spacing: 6) {
                                    AsyncImage(url: item.thumbnailUrl.flatMap(URL.init(string:))) { phase in
                                        if let image = phase.image {
                                            image.resizable().scaledToFill()
                                        } else {
                                            AppTheme.subtle
                                                .overlay { ProgressView() }
                                        }
                                    }
                                    .frame(width: 112, height: 142)
                                    .clipped()
                                    .clipShape(RoundedRectangle(cornerRadius: 14))
                                    .overlay(alignment: .topTrailing) {
                                        Image(
                                            systemName: selectedBoardIDs.contains(item.id)
                                                ? "checkmark.circle.fill"
                                                : "circle"
                                        )
                                        .font(.title3)
                                        .foregroundStyle(
                                            selectedBoardIDs.contains(item.id)
                                                ? AppTheme.wine
                                                : .white
                                        )
                                        .padding(6)
                                    }
                                    Text(item.title)
                                        .font(.caption)
                                        .lineLimit(2)
                                        .frame(width: 112, alignment: .leading)
                                }
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }

                Button("保存所选到本机审美库") {
                    Task { await importBoardItems() }
                }
                .font(.subheadline.weight(.semibold))
                .disabled(selectedBoardIDs.isEmpty || isWorking)
            }
        }
        .card()
    }

    private var uploadCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("直接选择参考图", systemImage: "photo.on.rectangle.angled")
                .font(.headline)
            Text("至少 3 张，推荐 6–10 张，最多 15 张。")
                .font(.footnote)
                .foregroundStyle(AppTheme.muted)
            PhotosPicker(
                selection: $selectedItems,
                maxSelectionCount: 15,
                matching: .images
            ) {
                Label("从相册选择", systemImage: "plus")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 13)
                    .background(AppTheme.blush)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            }
            Text("已保存到本机：\(localPaths.count) 张")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(AppTheme.wine)
        }
        .card()
    }

    @MainActor
    private func previewBoard() async {
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            let preview = try await APIClient.shared.previewBoard(url: boardURL)
            boardMessage = preview.message
            boardItems = preview.items
            selectedBoardIDs = Set(preview.items.prefix(10).map(\.id))
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func importBoardItems() async {
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            let remaining = max(0, 15 - localPaths.count)
            let selected = boardItems
                .filter { selectedBoardIDs.contains($0.id) }
                .prefix(remaining)
            for item in selected {
                guard
                    let urlString = item.thumbnailUrl,
                    let url = URL(string: urlString)
                else { continue }
                let (data, response) = try await URLSession.shared.data(from: url)
                guard
                    let http = response as? HTTPURLResponse,
                    200..<300 ~= http.statusCode,
                    !data.isEmpty
                else { continue }
                let path = try await LocalImageStore.shared.save(data, in: .references)
                localPaths.append(path)
                modelContext.insert(
                    LocalReference(
                        sourceType: "xiaohongshuBoard",
                        sourceURL: urlString,
                        localImagePath: path
                    )
                )
            }
            try modelContext.save()
            boardMessage = String(localized: "所选公开图片已保存到本机审美库。")
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func importPhotos(_ items: [PhotosPickerItem]) async {
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            for item in items where localPaths.count < 15 {
                guard let data = try await item.loadTransferable(type: Data.self) else { continue }
                let path = try await LocalImageStore.shared.save(data, in: .references)
                localPaths.append(path)
                modelContext.insert(LocalReference(sourceType: "directUpload", localImagePath: path))
            }
            try modelContext.save()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    @MainActor
    private func createProfile() async {
        isWorking = true
        errorMessage = nil
        defer { isWorking = false }
        do {
            var urls: [URL] = []
            for path in localPaths {
                urls.append(try await LocalImageStore.shared.url(for: path))
            }
            // editVersions is newest-first. Keep the newest useful signals,
            // then send them oldest-to-newest as a stable preference timeline.
            let calibration = Array(
                editVersions.compactMap(\.calibrationSignal).prefix(12).reversed()
            )
            let profile = try await APIClient.shared.createProfile(
                referenceURLs: urls,
                calibrationHistory: calibration
            )
            modelContext.insert(try LocalAestheticProfile(dto: profile))
            try modelContext.save()
            generatedProfile = profile
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
