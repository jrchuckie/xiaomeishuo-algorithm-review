import SwiftData
import SwiftUI

@main
struct XiaomeishuoApp: App {
    private let container: ModelContainer = {
        do {
            return try ModelContainer(
                for: LocalAestheticProfile.self,
                LocalReference.self,
                LocalEditSession.self,
                LocalEditVersion.self,
                LocalMedicalSession.self
            )
        } catch {
            fatalError("无法初始化本地数据库：\(error.localizedDescription)")
        }
    }()

    var body: some Scene {
        WindowGroup {
            RootView()
        }
        .modelContainer(container)
    }
}
