// Where the subject of a picture is (macOS Vision, on-device), for lp-compose's subject-anchored crops.
// Reads image paths, one per line, on stdin; prints one JSON object per image:
// {"path", "w", "h", "faces": [[x0, y0, x1, y1]], "people": [[...]], "salient": [x0, y0, x1, y1] | null}
// Boxes are pixels, origin top-left. Nothing leaves the machine.
import Foundation
import Vision
import ImageIO

func pixelBox(_ r: CGRect, _ w: Int, _ h: Int) -> [Int] {
    let x0 = Int((r.minX * CGFloat(w)).rounded()), x1 = Int((r.maxX * CGFloat(w)).rounded())
    let y0 = Int(((1 - r.maxY) * CGFloat(h)).rounded()), y1 = Int(((1 - r.minY) * CGFloat(h)).rounded())
    return [x0, y0, x1, y1]
}

func locate(_ path: String) -> [String: Any] {
    var out: [String: Any] = ["path": path, "faces": [], "people": [], "salient": NSNull()]
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        out["error"] = "unreadable"
        return out
    }
    let w = img.width, h = img.height
    out["w"] = w
    out["h"] = h
    let faces = VNDetectFaceRectanglesRequest()
    let people = VNDetectHumanRectanglesRequest()
    let salient = VNGenerateAttentionBasedSaliencyImageRequest()
    do {
        try VNImageRequestHandler(cgImage: img, options: [:]).perform([faces, people, salient])
    } catch {
        out["error"] = "\(error)"
        return out
    }
    out["faces"] = (faces.results ?? []).map { pixelBox($0.boundingBox, w, h) }
    out["people"] = (people.results ?? []).map { pixelBox($0.boundingBox, w, h) }
    if let obs = salient.results?.first, let objs = obs.salientObjects, !objs.isEmpty {
        let u = objs.map { $0.boundingBox }.reduce(objs[0].boundingBox) { $0.union($1) }
        out["salient"] = pixelBox(u, w, h)
    }
    return out
}

while let line = readLine() {
    let path = line.trimmingCharacters(in: .whitespaces)
    if path.isEmpty { continue }
    if let data = try? JSONSerialization.data(withJSONObject: locate(path)), let s = String(data: data, encoding: .utf8) {
        print(s)
    }
}
