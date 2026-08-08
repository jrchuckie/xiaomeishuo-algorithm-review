import SwiftData
import SwiftUI

struct RootView: View {
    @Query(sort: \LocalAestheticProfile.updatedAt, order: .reverse)
    private var profiles: [LocalAestheticProfile]

    var body: some View {
        Group {
            if let profile = profiles.first {
                MainTabView(profile: profile)
            } else {
                NavigationStack {
                    WelcomeView()
                }
            }
        }
        .tint(AppTheme.wine)
    }
}

private struct MainTabView: View {
    let profile: LocalAestheticProfile

    var body: some View {
        TabView {
            NavigationStack {
                HomeView(profile: profile)
            }
            .tabItem {
                Label("探索", systemImage: "sparkles")
            }

            NavigationStack {
                if let dto = profile.dto {
                    ProfileView(profile: dto)
                }
            }
            .tabItem {
                Label("我的审美", systemImage: "person.crop.circle")
            }

            NavigationStack {
                MedicalStartView(profile: profile)
            }
            .tabItem {
                Label("方案", systemImage: "list.clipboard")
            }
        }
        .tint(AppTheme.wine)
    }
}
