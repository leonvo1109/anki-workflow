#!/usr/bin/env swift
// On-device Bildklassifikation via Apple Vision (kein Download, nur macOS).
// Ausgabe: JSON-Array [{label, confidence}, ...]
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1 else {
    print("[]")
    exit(0)
}

let path = CommandLine.arguments[1]
let url = URL(fileURLWithPath: path)

guard let image = NSImage(contentsOf: url),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("[]")
    exit(0)
}

let request = VNClassifyImageRequest()
let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])

do {
    try handler.perform([request])
    let results = (request.results as? [VNClassificationObservation]) ?? []
    let top = results.prefix(5).map { obs in
        ["label": obs.identifier, "confidence": obs.confidence] as [String: Any]
    }
    let data = try JSONSerialization.data(withJSONObject: top)
    if let json = String(data: data, encoding: .utf8) {
        print(json)
    } else {
        print("[]")
    }
} catch {
    print("[]")
}
