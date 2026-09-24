// On-device text recognition (macOS Vision), for `lp-corpus ocr`.
// Reads image paths, one per line, on stdin; prints one JSON object per image:
// {"path", "w", "h", "lines": [{"text", "conf", "box": [x0, y0, x1, y1], "words": [{"text", "box"}]}]}
// Boxes are pixels, origin top-left. Nothing leaves the machine.
import Foundation
import Vision
import ImageIO

func pixelBox(_ r: CGRect, _ w: Int, _ h: Int) -> [Int] {
    let x0 = Int((r.minX * CGFloat(w)).rounded()), x1 = Int((r.maxX * CGFloat(w)).rounded())
    let y0 = Int(((1 - r.maxY) * CGFloat(h)).rounded()), y1 = Int(((1 - r.minY) * CGFloat(h)).rounded())
    return [x0, y0, x1, y1]
}

func recognise(_ path: String) -> [String: Any] {
    var out: [String: Any] = ["path": path, "lines": []]
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        out["error"] = "unreadable"
        return out
    }
    let w = img.width, h = img.height
    out["w"] = w
    out["h"] = h
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false  // UI strings, prices and model names are not dictionary words
    req.minimumTextHeight = 0.008
    do {
        try VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    } catch {
        out["error"] = "\(error)"
        return out
    }
    var lines: [[String: Any]] = []
    for obs in req.results ?? [] {
        guard let top = obs.topCandidates(1).first else { continue }
        let s = top.string
        var words: [[String: Any]] = []
        var i = s.startIndex
        while i < s.endIndex {
            while i < s.endIndex && s[i] == " " { i = s.index(after: i) }
            var j = i
            while j < s.endIndex && s[j] != " " { j = s.index(after: j) }
            if i < j, let b = try? top.boundingBox(for: i..<j) {
                words.append(["text": String(s[i..<j]), "box": pixelBox(b.boundingBox, w, h)])
            }
            i = j
        }
        lines.append(["text": s, "conf": Double(top.confidence), "box": pixelBox(obs.boundingBox, w, h), "words": words])
    }
    out["lines"] = lines
    return out
}

while let line = readLine() {
    let path = line.trimmingCharacters(in: .whitespaces)
    if path.isEmpty { continue }
    let result = autoreleasepool { recognise(path) }
    if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
       let text = String(data: data, encoding: .utf8) {
        print(text)
        fflush(stdout)
    }
}
