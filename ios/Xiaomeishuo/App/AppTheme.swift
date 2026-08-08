import SwiftUI

enum AppTheme {
    // Figma: XMS · Silk Intelligence UI System v1
    static let wine = Color(red: 0.4078, green: 0.2039, blue: 0.2510)
    static let wineDeep = Color(red: 0.3020, green: 0.1451, blue: 0.1843)
    static let blush = Color(red: 0.9725, green: 0.9098, blue: 0.9216)
    static let silk = Color(red: 0.9373, green: 0.8118, blue: 0.8353)
    static let paper = Color(red: 0.9882, green: 0.9804, blue: 0.9804)
    static let surface = Color.white
    static let subtle = Color(red: 0.9686, green: 0.9490, blue: 0.9490)
    static let ink = Color(red: 0.1451, green: 0.1216, blue: 0.1294)
    static let muted = Color(red: 0.3176, green: 0.2824, blue: 0.2941)
    static let tertiary = Color(red: 0.5098, green: 0.4667, blue: 0.4784)
    static let border = Color(red: 0.9333, green: 0.8980, blue: 0.9020)
    static let safe = Color(red: 0.2784, green: 0.4510, blue: 0.3882)
    static let caution = Color(red: 0.5451, green: 0.3686, blue: 0.1451)

    enum Spacing {
        static let xxs: CGFloat = 4
        static let xs: CGFloat = 8
        static let sm: CGFloat = 12
        static let md: CGFloat = 16
        static let lg: CGFloat = 20
        static let xl: CGFloat = 24
        static let xxl: CGFloat = 32
        static let xxxl: CGFloat = 40
    }

    enum Radius {
        static let xs: CGFloat = 6
        static let sm: CGFloat = 10
        static let md: CGFloat = 16
        static let lg: CGFloat = 24
        static let xl: CGFloat = 32
    }
}

struct PrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .frame(minHeight: 52)
            .padding(.horizontal, 24)
            .background(AppTheme.wine.opacity(configuration.isPressed ? 0.78 : 1))
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.md, style: .continuous))
    }
}

struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(AppTheme.wine)
            .frame(maxWidth: .infinity)
            .frame(minHeight: 50)
            .background(AppTheme.surface.opacity(configuration.isPressed ? 0.7 : 1))
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.md, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: AppTheme.Radius.md, style: .continuous)
                    .stroke(AppTheme.border, lineWidth: 1)
            }
    }
}

struct CardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(AppTheme.Spacing.lg)
            .background(AppTheme.surface)
            .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.lg, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: AppTheme.Radius.lg, style: .continuous)
                    .stroke(AppTheme.border, lineWidth: 1)
            }
    }
}

extension View {
    func card() -> some View {
        modifier(CardModifier())
    }

    func silkScreen() -> some View {
        background(AppTheme.paper.ignoresSafeArea())
            .foregroundStyle(AppTheme.ink)
    }
}

struct SilkHeader: View {
    let title: LocalizedStringKey
    let subtitle: LocalizedStringKey

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            Image("SilkHorizon")
                .resizable()
                .scaledToFill()
                .opacity(0.42)
                .frame(height: 138)
                .clipped()
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.title.bold())
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(AppTheme.muted)
            }
            .padding(.horizontal, AppTheme.Spacing.xl)
            .padding(.bottom, AppTheme.Spacing.md)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 138)
    }
}
