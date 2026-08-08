import Foundation

actor LocalImageStore {
    static let shared = LocalImageStore()

    enum Folder: String {
        case references
        case editSources = "edit-sources"
        case editResults = "edit-results"
        case medicalSources = "medical-sources"
        case medicalResults = "medical-results"
    }

    private let fileManager = FileManager.default

    func save(_ data: Data, in folder: Folder, fileExtension: String = "jpg") throws -> String {
        let directory = try directoryURL(for: folder)
        let filename = "\(UUID().uuidString.lowercased()).\(fileExtension)"
        let url = directory.appendingPathComponent(filename)
        try data.write(to: url, options: [.atomic, .completeFileProtection])
        return "\(folder.rawValue)/\(filename)"
    }

    func url(for relativePath: String) throws -> URL {
        try baseDirectory().appendingPathComponent(relativePath)
    }

    func copy(relativePath: String, to folder: Folder) throws -> String {
        let source = try url(for: relativePath)
        let data = try Data(contentsOf: source)
        return try save(data, in: folder)
    }

    private func baseDirectory() throws -> URL {
        let base = try fileManager.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        ).appendingPathComponent("Xiaomeishuo", isDirectory: true)
        try fileManager.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    private func directoryURL(for folder: Folder) throws -> URL {
        let directory = try baseDirectory().appendingPathComponent(folder.rawValue, isDirectory: true)
        try fileManager.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory
    }
}
