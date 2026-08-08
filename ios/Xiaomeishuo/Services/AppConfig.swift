import Foundation

enum AppConfig {
    static let apiBaseURL: URL = {
        if let override = ProcessInfo.processInfo.environment["XMS_API_BASE_URL"],
           let url = URL(string: override),
           !override.isEmpty {
            return url
        }
        if let host = Bundle.main.object(forInfoDictionaryKey: "XMSAPIHost") as? String,
           !host.isEmpty,
           !host.contains("$("),
           let url = URL(string: "https://\(host)") {
            return url
        }
        #if DEBUG
        return URL(string: "http://127.0.0.1:8000")!
        #else
        preconditionFailure("XMSAPIBaseURL is not configured")
        #endif
    }()

    static let appAccessToken: String? = {
        if let override = ProcessInfo.processInfo.environment["XMS_APP_ACCESS_TOKEN"],
           !override.isEmpty {
            return override
        }
        guard let configured = Bundle.main.object(forInfoDictionaryKey: "XMSAppAccessToken") as? String,
              !configured.isEmpty,
              !configured.contains("$(") else {
            return nil
        }
        return configured
    }()
}
