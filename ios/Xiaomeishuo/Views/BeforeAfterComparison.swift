import SwiftUI
import UIKit

struct BeforeAfterComparison: View {
    let before: UIImage
    let after: UIImage
    @Binding var value: Double

    var body: some View {
        GeometryReader { geometry in
            let width = geometry.size.width
            ZStack(alignment: .leading) {
                Image(uiImage: before)
                    .resizable()
                    .scaledToFill()
                    .frame(width: width, height: geometry.size.height)
                    .clipped()

                Image(uiImage: after)
                    .resizable()
                    .scaledToFill()
                    .frame(width: width, height: geometry.size.height)
                    .clipped()
                    .mask(alignment: .leading) {
                        Rectangle().frame(width: width * value)
                    }

                Rectangle()
                    .fill(.white)
                    .frame(width: 2)
                    .shadow(radius: 3)
                    .offset(x: max(0, width * value - 1))

                Image(systemName: "arrow.left.and.right.circle.fill")
                    .font(.title)
                    .foregroundStyle(.white, AppTheme.wine)
                    .offset(x: max(0, width * value - 16))

                comparisonLabel("AFTER", alignment: .leading)
                comparisonLabel("BEFORE", alignment: .trailing)
            }
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { gesture in
                        value = min(max(gesture.location.x / max(width, 1), 0), 1)
                    }
            )
        }
        .aspectRatio(CGSize(width: before.size.width, height: before.size.height), contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.lg))
        .overlay {
            RoundedRectangle(cornerRadius: AppTheme.Radius.lg)
                .stroke(AppTheme.border, lineWidth: 1)
        }
    }

    private func comparisonLabel(_ text: LocalizedStringKey, alignment: Alignment) -> some View {
        Text(text)
            .font(.caption2.bold())
            .foregroundStyle(.white)
            .padding(.horizontal, 9)
            .padding(.vertical, 6)
            .background(.black.opacity(0.55))
            .clipShape(Capsule())
            .frame(
                maxWidth: .infinity,
                maxHeight: .infinity,
                alignment: alignment == .leading ? .topLeading : .topTrailing
            )
            .padding(12)
    }
}
