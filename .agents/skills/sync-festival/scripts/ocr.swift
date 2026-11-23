// OCR helper: prints the text Apple's Vision framework reads in each image.
// Usage: swift tmp/ocr.swift <image-path> [<image-path> ...]
// Output: one JSON object per line: {"file": "...", "text": "..."}
import AppKit
import Foundation
import Vision

func recognize(_ path: String) -> String {
    guard let image = NSImage(contentsOfFile: path),
          let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        return ""
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["vi-VN", "en-US"]
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    do {
        try handler.perform([request])
    } catch {
        return ""
    }
    let lines = (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    return lines.joined(separator: "\n")
}

for path in CommandLine.arguments.dropFirst() {
    let text = recognize(path)
    let payload: [String: String] = ["file": path, "text": text]
    if let data = try? JSONSerialization.data(withJSONObject: payload),
       let line = String(data: data, encoding: .utf8) {
        print(line)
    }
}
