#!/usr/bin/env swift
import AppKit
import Foundation
import Vision

struct Match {
    let text: String
    let x: CGFloat
    let y: CGFloat
    let width: CGFloat
    let height: CGFloat
    let confidence: Float
}

func usage() -> Never {
    fputs("""
    Usage:
      vision-find-text.swift <screenshot.png> <text> [--scale 2] [--exact]

    Finds recognized text in a screenshot using macOS Vision and prints both:
      - screenshot pixel bounds
      - global logical cliclick coordinate for the center point

    By default, matching is case-insensitive substring matching. Use --exact
    for case-insensitive exact line matching. On Retina displays, --scale 2 is
    usually correct because screenshots are physical pixels and cliclick uses
    logical points.

    Example:
      scripts/vision-find-text.swift /tmp/screen.png Workflows

    """, stderr)
    exit(2)
}

let args = Array(CommandLine.arguments.dropFirst())
guard args.count >= 2 else { usage() }

let imagePath = args[0]
let needle = args[1].lowercased()
var scale: CGFloat = 2.0
var exact = false

var i = 2
while i < args.count {
    switch args[i] {
    case "--scale":
        guard i + 1 < args.count, let parsed = Double(args[i + 1]), parsed > 0 else {
            usage()
        }
        scale = CGFloat(parsed)
        i += 2
    case "--exact":
        exact = true
        i += 1
    default:
        usage()
    }
}

let imageURL = URL(fileURLWithPath: imagePath)
guard
    let image = NSImage(contentsOf: imageURL),
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let cgImage = bitmap.cgImage
else {
    fputs("Could not load image: \(imagePath)\n", stderr)
    exit(1)
}

let imageWidth = CGFloat(cgImage.width)
let imageHeight = CGFloat(cgImage.height)
var matches: [Match] = []

let request = VNRecognizeTextRequest { request, error in
    if let error {
        fputs("Vision OCR failed: \(error)\n", stderr)
        exit(1)
    }

    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        return
    }

    for observation in observations {
        guard let candidate = observation.topCandidates(1).first else { continue }
        let text = candidate.string
        let haystack = text.lowercased()
        let isMatch = exact ? haystack == needle : haystack.contains(needle)
        guard isMatch else { continue }

        let box = observation.boundingBox
        let x = box.origin.x * imageWidth
        let y = (1.0 - box.origin.y - box.height) * imageHeight
        let width = box.width * imageWidth
        let height = box.height * imageHeight
        matches.append(Match(
            text: text,
            x: x,
            y: y,
            width: width,
            height: height,
            confidence: candidate.confidence
        ))
    }
}

request.recognitionLevel = .accurate
request.usesLanguageCorrection = false

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try handler.perform([request])

guard !matches.isEmpty else {
    fputs("No OCR match for: \(args[1])\n", stderr)
    exit(1)
}

print("text\tscreenshot_x\tscreenshot_y\tscreenshot_w\tscreenshot_h\tcenter_x\tcenter_y\tcliclick_x\tcliclick_y\tconfidence")
for match in matches {
    let centerX = match.x + match.width / 2.0
    let centerY = match.y + match.height / 2.0
    let clickX = centerX / scale
    let clickY = centerY / scale
    var fields: [String] = []
    fields.append(match.text)
    fields.append(String(Int(round(match.x))))
    fields.append(String(Int(round(match.y))))
    fields.append(String(Int(round(match.width))))
    fields.append(String(Int(round(match.height))))
    fields.append(String(Int(round(centerX))))
    fields.append(String(Int(round(centerY))))
    fields.append(String(Int(round(clickX))))
    fields.append(String(Int(round(clickY))))
    fields.append(String(format: "%.3f", match.confidence))
    print(fields.joined(separator: "\t"))
}
