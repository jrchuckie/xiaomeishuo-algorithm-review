import SwiftUI

struct WelcomeView: View {
    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 28) {
                    Text("IDEAL ME")
                        .font(.caption.weight(.semibold))
                        .tracking(2)
                        .foregroundStyle(AppTheme.wine)

                    Text("先读懂你喜欢的美，\n再修你自己的照片")
                        .font(.system(size: 38, weight: .bold, design: .rounded))
                        .foregroundStyle(AppTheme.ink)

                    Text("导入小红书公开收藏夹，或直接选择 3–15 张参考图。小美说会建立只保存在这台 iPhone 上的个人审美档案。")
                        .font(.body)
                        .foregroundStyle(AppTheme.muted)
                        .lineSpacing(5)

                    VStack(alignment: .leading, spacing: 14) {
                        Label("审美档案和修图记录只存在本机", systemImage: "iphone")
                        Label("图片只在生成时发送给模型", systemImage: "lock.shield")
                        Label("MVP 无登录，删除 App 会删除本地档案", systemImage: "info.circle")
                    }
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.ink)
                    .card()

                    NavigationLink {
                        ReferenceSetupView()
                    } label: {
                        Text("建立我的审美档案")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                }
                .padding(24)
                .padding(.top, 28)
            }
        }
        .navigationBarHidden(true)
    }
}

