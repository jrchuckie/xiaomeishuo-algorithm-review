import SwiftUI

struct HomeView: View {
    let profile: LocalAestheticProfile

    var body: some View {
        ZStack {
            AppTheme.paper.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: AppTheme.Spacing.lg) {
                    SilkHeader(
                        title: "审美档案",
                        subtitle: "从你喜欢什么开始，持续校准"
                    )
                    if let dto = profile.dto {
                        NavigationLink {
                            ProfileView(profile: dto)
                        } label: {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("MY AESTHETIC")
                                    .font(.caption.weight(.semibold))
                                    .tracking(1.6)
                                Text(dto.primaryDirection)
                                    .font(.title2.bold())
                                Text("\(dto.sourceCount) 张参考图 · \(dto.secondaryDirection)")
                                    .font(.subheadline)
                                ProgressView(value: min(Double(dto.sourceCount) / 10, 1))
                                    .tint(AppTheme.wine)
                            }
                            .foregroundStyle(AppTheme.ink)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .card()
                        }

                        NavigationLink {
                            EditorStartView(profile: dto)
                        } label: {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("NEXT · 个性化修图")
                                    .font(.caption.weight(.semibold))
                                    .tracking(1.2)
                                Text("用这份审美档案修一张照片")
                                    .font(.headline)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .buttonStyle(PrimaryButtonStyle())

                        NavigationLink {
                            MedicalStartView(profile: profile)
                        } label: {
                            Label("进入医美决策支持", systemImage: "list.clipboard")
                        }
                        .buttonStyle(SecondaryButtonStyle())
                    }

                    NavigationLink {
                        ReferenceSetupView()
                    } label: {
                        Label("重新建立审美档案", systemImage: "photo.stack")
                    }
                    .font(.subheadline.weight(.semibold))

                    Text("照片、画像与历史保存在这台 iPhone；云端只完成你主动发起的即时 AI 运算。")
                        .font(.caption)
                        .foregroundStyle(AppTheme.tertiary)
                }
                .padding(.bottom, AppTheme.Spacing.xl)
            }
        }
        .navigationBarHidden(true)
    }
}
