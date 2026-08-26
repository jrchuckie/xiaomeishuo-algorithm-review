import Foundation
import SwiftUI
import UIKit

struct EffectCallout: Identifiable {
    let id: String
    let label: String
    let anchorX: CGFloat
    let anchorY: CGFloat
    let labelX: CGFloat
    let labelY: CGFloat
}

enum EffectCalloutFactory {
    static func medical(plan: MedicalPlanDTO) -> [EffectCallout] {
        let candidates = plan.candidates.filter { $0.enabled && $0.priority != "avoid" }
        return Array(candidates.prefix(3).enumerated()).map { index, candidate in
            make(
                id: candidate.id,
                area: candidate.area,
                goal: candidate.goal,
                fallbackIndex: index
            )
        }
    }

    private static func make(
        id: String,
        area: String,
        goal: String,
        fallbackIndex: Int
    ) -> EffectCallout {
        let label = conciseLabel(area: area, goal: goal)
        let normalized = area.lowercased()
        if normalized.contains("下颌") || normalized.contains("轮廓") || normalized.contains("jaw") {
            return EffectCallout(
                id: id,
                label: label,
                anchorX: 0.80,
                anchorY: 0.70,
                labelX: 0.63,
                labelY: 0.88
            )
        }
        if normalized.contains("下巴") || normalized.contains("颏") || normalized.contains("chin") {
            return EffectCallout(
                id: id,
                label: label,
                anchorX: 0.50,
                anchorY: 0.80,
                labelX: 0.33,
                labelY: 0.93
            )
        }
        if normalized.contains("面中") || normalized.contains("鼻基底") || normalized.contains("midface") {
            return EffectCallout(
                id: id,
                label: label,
                anchorX: 0.68,
                anchorY: 0.53,
                labelX: 0.69,
                labelY: 0.24
            )
        }
        if normalized.contains("太阳穴") || normalized.contains("颞") || normalized.contains("temple") {
            return EffectCallout(
                id: id,
                label: label,
                anchorX: 0.20,
                anchorY: 0.35,
                labelX: 0.34,
                labelY: 0.17
            )
        }
        if normalized.contains("唇") || normalized.contains("口") || normalized.contains("lip") {
            return EffectCallout(
                id: id,
                label: label,
                anchorX: 0.50,
                anchorY: 0.63,
                labelX: 0.38,
                labelY: 0.82
            )
        }
        if normalized.contains("鼻") || normalized.contains("nose") {
            return EffectCallout(
                id: id,
                label: label,
                anchorX: 0.50,
                anchorY: 0.52,
                labelX: 0.44,
                labelY: 0.20
            )
        }
        if normalized.contains("眼") || normalized.contains("eye") {
            return EffectCallout(
                id: id,
                label: label,
                anchorX: 0.50,
                anchorY: 0.37,
                labelX: 0.46,
                labelY: 0.17
            )
        }
        let fallbackAnchors: [(CGFloat, CGFloat, CGFloat, CGFloat)] = [
            (0.72, 0.58, 0.66, 0.22),
            (0.28, 0.58, 0.35, 0.82),
            (0.50, 0.75, 0.48, 0.92),
        ]
        let fallback = fallbackAnchors[min(fallbackIndex, fallbackAnchors.count - 1)]
        return EffectCallout(
            id: id,
            label: label,
            anchorX: fallback.0,
            anchorY: fallback.1,
            labelX: fallback.2,
            labelY: fallback.3
        )
    }

    private static func conciseLabel(area: String, goal: String) -> String {
        let trimmed = goal.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty {
            return String(trimmed.prefix(14))
        }
        return "\(area)更协调"
    }
}

struct EffectExplanationCard: View {
    let before: UIImage
    let after: UIImage
    let callouts: [EffectCallout]

    var body: some View {
        GeometryReader { geometry in
            let headerHeight = geometry.size.height * 0.13
            let imageHeight = geometry.size.height * 0.72
            let footerHeight = geometry.size.height - headerHeight - imageHeight

            VStack(spacing: 0) {
                VStack(spacing: 4) {
                    Text("医美效果模拟 · 前后对比")
                        .font(.system(size: 22, weight: .bold, design: .rounded))
                        .foregroundStyle(AppTheme.ink)
                    Text("变化说明图")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.wine)
                }
                .frame(maxWidth: .infinity)
                .frame(height: headerHeight)

                HStack(spacing: 2) {
                    portraitPanel(image: before, label: "改善前")
                    ZStack {
                        portraitPanel(image: after, label: "目标模拟")
                        EffectCalloutOverlay(callouts: callouts)
                    }
                }
                .frame(height: imageHeight)
                .clipped()

                VStack(spacing: 4) {
                    Text("标识仅用于说明变化区域")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(AppTheme.muted)
                    Text("仅用于审美目标沟通，不代表真实治疗效果")
                        .font(.caption2)
                        .foregroundStyle(AppTheme.tertiary)
                }
                .frame(maxWidth: .infinity)
                .frame(height: footerHeight)
            }
            .background(AppTheme.paper)
        }
        .aspectRatio(4 / 5, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: AppTheme.Radius.lg, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: AppTheme.Radius.lg, style: .continuous)
                .stroke(AppTheme.border, lineWidth: 1)
        }
    }

    private func portraitPanel(image: UIImage, label: LocalizedStringKey) -> some View {
        GeometryReader { geometry in
            ZStack(alignment: .topLeading) {
                Image(uiImage: image)
                    .resizable()
                    .scaledToFill()
                    .frame(width: geometry.size.width, height: geometry.size.height)
                    .clipped()
                Text(label)
                    .font(.caption.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 6)
                    .background(.black.opacity(0.56))
                    .clipShape(Capsule())
                    .padding(10)
            }
        }
    }
}

private struct EffectCalloutOverlay: View {
    let callouts: [EffectCallout]

    var body: some View {
        GeometryReader { geometry in
            Canvas { context, size in
                for callout in callouts {
                    let start = CGPoint(
                        x: size.width * callout.labelX,
                        y: size.height * callout.labelY
                    )
                    let end = CGPoint(
                        x: size.width * callout.anchorX,
                        y: size.height * callout.anchorY
                    )
                    drawArrow(context: &context, from: start, to: end)
                }
            }

            ForEach(callouts) { callout in
                Text(callout.label)
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(.white)
                    .lineLimit(2)
                    .minimumScaleFactor(0.72)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 5)
                    .background(.black.opacity(0.66))
                    .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 7, style: .continuous)
                            .stroke(.white.opacity(0.85), lineWidth: 0.8)
                    }
                    .frame(maxWidth: geometry.size.width * 0.48)
                    .position(
                        x: geometry.size.width * callout.labelX,
                        y: geometry.size.height * callout.labelY
                    )
            }
        }
    }

    private func drawArrow(
        context: inout GraphicsContext,
        from start: CGPoint,
        to end: CGPoint
    ) {
        var line = Path()
        line.move(to: start)
        line.addLine(to: end)
        context.stroke(line, with: .color(.black.opacity(0.48)), lineWidth: 4)
        context.stroke(line, with: .color(.white), lineWidth: 2)

        let angle = atan2(end.y - start.y, end.x - start.x)
        let arrowLength: CGFloat = 10
        let spread: CGFloat = .pi / 7
        var head = Path()
        head.move(to: end)
        head.addLine(
            to: CGPoint(
                x: end.x - arrowLength * cos(angle - spread),
                y: end.y - arrowLength * sin(angle - spread)
            )
        )
        head.move(to: end)
        head.addLine(
            to: CGPoint(
                x: end.x - arrowLength * cos(angle + spread),
                y: end.y - arrowLength * sin(angle + spread)
            )
        )
        context.stroke(head, with: .color(.black.opacity(0.48)), lineWidth: 4)
        context.stroke(head, with: .color(.white), lineWidth: 2)

        let marker = Path(ellipseIn: CGRect(x: end.x - 4, y: end.y - 4, width: 8, height: 8))
        context.fill(marker, with: .color(.white))
        context.stroke(marker, with: .color(.black.opacity(0.5)), lineWidth: 1)
    }
}

@MainActor
enum EffectExplanationRenderer {
    static func render(
        before: UIImage,
        after: UIImage,
        callouts: [EffectCallout]
    ) -> UIImage? {
        let content = EffectExplanationCard(
            before: before,
            after: after,
            callouts: callouts
        )
        .frame(width: 390, height: 488)

        let renderer = ImageRenderer(content: content)
        renderer.scale = 3
        renderer.isOpaque = true
        return renderer.uiImage
    }
}
