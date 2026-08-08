import SwiftUI

struct ProfileView: View {
    let profile: AestheticProfileDTO
    var isNewProfile = false

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Text("IDEAL ME / 01")
                        .font(.caption.weight(.semibold))
                        .tracking(1.8)
                        .foregroundStyle(AppTheme.wine)

                    Text(profile.primaryDirection)
                        .font(.system(size: 36, weight: .bold, design: .rounded))

                    Text(profile.secondaryDirection)
                        .font(.headline)
                        .foregroundStyle(AppTheme.wine)

                    Text("这只是对你所选样本的审美总结，不等于要求你保持原貌，也不是固定的美学标准。")
                        .foregroundStyle(AppTheme.muted)

                    ForEach(profile.insights) { insight in
                        VStack(alignment: .leading, spacing: 10) {
                            Text(insight.region.uppercased())
                                .font(.caption.weight(.bold))
                                .foregroundStyle(AppTheme.wine)
                            Text(insight.title)
                                .font(.title3.bold())
                            Text(insight.summary)
                                .foregroundStyle(AppTheme.muted)
                            Text("证据：\(insight.evidence.note)")
                                .font(.footnote)
                                .foregroundStyle(AppTheme.muted)
                        }
                        .card()
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        Text("明确不是你要的")
                            .font(.headline)
                        FlowLayout(items: profile.antiTargets)
                    }
                    .card()

                    NavigationLink {
                        EditorStartView(profile: profile)
                    } label: {
                        Text("按这份档案修一张照片")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                }
                .padding(24)
            }
        }
        .navigationTitle(isNewProfile ? "审美画像已生成" : "我的审美")
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct FlowLayout: View {
    let items: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(items, id: \.self) { item in
                Text(item)
                    .font(.subheadline.weight(.semibold))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(AppTheme.blush)
                    .clipShape(Capsule())
            }
        }
    }
}
