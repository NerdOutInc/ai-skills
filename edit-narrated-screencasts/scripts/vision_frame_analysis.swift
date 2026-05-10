#!/usr/bin/env swift
import AppKit
import Foundation
import Vision

struct FrameEntry {
    let id: String
    let time: Double
    let path: String
}

func usage() -> Never {
    fputs("""
    Usage:
      vision_frame_analysis.swift --manifest frames.jsonl --out vision-frames.jsonl [--ocr-level fast|accurate]

    Reads JSONL frame manifest entries with id, time, and path fields. Writes
    JSONL Apple Vision observations with OCR text and feature-print distance
    from the previous usable frame.

    """, stderr)
    exit(2)
}

func jsonObject(_ data: [String: Any]) -> String {
    do {
        let encoded = try JSONSerialization.data(withJSONObject: data, options: [.sortedKeys])
        return String(data: encoded, encoding: .utf8) ?? "{}"
    } catch {
        return "{\"error\":\"Could not encode JSON: \(error)\"}"
    }
}

func parseArgs() -> (manifest: String, out: String, level: VNRequestTextRecognitionLevel) {
    let args = CommandLine.arguments
    var manifest: String?
    var out: String?
    var level: VNRequestTextRecognitionLevel = .fast
    var index = 1
    while index < args.count {
        switch args[index] {
        case "--manifest":
            guard index + 1 < args.count else { usage() }
            manifest = args[index + 1]
            index += 2
        case "--out":
            guard index + 1 < args.count else { usage() }
            out = args[index + 1]
            index += 2
        case "--ocr-level":
            guard index + 1 < args.count else { usage() }
            switch args[index + 1] {
            case "fast":
                level = .fast
            case "accurate":
                level = .accurate
            default:
                usage()
            }
            index += 2
        case "--help", "-h":
            usage()
        default:
            usage()
        }
    }
    guard let manifest, let out else { usage() }
    return (manifest, out, level)
}

func readManifest(_ path: String) throws -> [FrameEntry] {
    let text = try String(contentsOfFile: path, encoding: .utf8)
    var entries: [FrameEntry] = []
    for (lineIndex, rawLine) in text.split(separator: "\n", omittingEmptySubsequences: false).enumerated() {
        let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
        if line.isEmpty { continue }
        guard let data = line.data(using: .utf8) else {
            throw NSError(domain: "Manifest", code: 1, userInfo: [NSLocalizedDescriptionKey: "Manifest line \(lineIndex + 1) is not UTF-8"])
        }
        guard
            let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
            let id = object["id"] as? String,
            let rawTime = object["time"],
            let framePath = object["path"] as? String
        else {
            throw NSError(domain: "Manifest", code: 1, userInfo: [NSLocalizedDescriptionKey: "Manifest line \(lineIndex + 1) must contain string id, numeric time, and string path"])
        }
        let time: Double
        if let value = rawTime as? Double {
            time = value
        } else if let value = rawTime as? NSNumber {
            time = value.doubleValue
        } else {
            throw NSError(domain: "Manifest", code: 1, userInfo: [NSLocalizedDescriptionKey: "Manifest line \(lineIndex + 1) has a non-numeric time"])
        }
        entries.append(FrameEntry(id: id, time: time, path: framePath))
    }
    if entries.isEmpty {
        throw NSError(domain: "Manifest", code: 1, userInfo: [NSLocalizedDescriptionKey: "Manifest has no frames: \(path)"])
    }
    return entries
}

func loadCGImage(_ path: String) -> (image: CGImage, width: Int, height: Int)? {
    guard
        let image = NSImage(contentsOfFile: path),
        let tiff = image.tiffRepresentation,
        let bitmap = NSBitmapImageRep(data: tiff),
        let cgImage = bitmap.cgImage
    else {
        return nil
    }
    return (cgImage, cgImage.width, cgImage.height)
}

func analyzeFrame(
    entry: FrameEntry,
    level: VNRequestTextRecognitionLevel,
    previousFeaturePrint: VNFeaturePrintObservation?
) -> (payload: [String: Any], featurePrint: VNFeaturePrintObservation?) {
    var payload: [String: Any] = [
        "id": entry.id,
        "time": entry.time,
        "path": entry.path,
    ]

    guard let loaded = loadCGImage(entry.path) else {
        payload["error"] = "Could not load frame image"
        return (payload, previousFeaturePrint)
    }

    payload["width"] = loaded.width
    payload["height"] = loaded.height

    let textRequest = VNRecognizeTextRequest()
    textRequest.recognitionLevel = level
    textRequest.usesLanguageCorrection = false

    let featureRequest = VNGenerateImageFeaturePrintRequest()
    featureRequest.imageCropAndScaleOption = .scaleFit

    do {
        let handler = VNImageRequestHandler(cgImage: loaded.image, options: [:])
        try handler.perform([textRequest, featureRequest])
    } catch {
        payload["error"] = "Vision analysis failed: \(error)"
        return (payload, previousFeaturePrint)
    }

    var observations: [[String: Any]] = []
    var textLines: [String] = []
    if let results = textRequest.results {
        for observation in results {
            guard let candidate = observation.topCandidates(1).first else { continue }
            let box = observation.boundingBox
            let x = box.origin.x * Double(loaded.width)
            let y = (1.0 - box.origin.y - box.height) * Double(loaded.height)
            let width = box.width * Double(loaded.width)
            let height = box.height * Double(loaded.height)
            observations.append([
                "text": candidate.string,
                "confidence": candidate.confidence,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "normalized": [
                    "x": box.origin.x,
                    "y": box.origin.y,
                    "width": box.width,
                    "height": box.height,
                ],
            ])
            textLines.append(candidate.string)
        }
    }

    payload["ocr_observations"] = observations
    payload["ocr_text"] = textLines.joined(separator: " ")
    if observations.isEmpty {
        payload["ocr_confidence"] = NSNull()
    } else {
        let total = observations.reduce(Float(0)) { partial, item in
            partial + ((item["confidence"] as? Float) ?? 0)
        }
        payload["ocr_confidence"] = total / Float(observations.count)
    }

    let featurePrint = featureRequest.results?.first as? VNFeaturePrintObservation
    if let previousFeaturePrint, let featurePrint {
        do {
            var distance = Float(0)
            try previousFeaturePrint.computeDistance(&distance, to: featurePrint)
            payload["feature_distance_from_previous"] = distance
        } catch {
            payload["feature_distance_from_previous"] = NSNull()
            payload["feature_distance_error"] = "\(error)"
        }
    } else {
        payload["feature_distance_from_previous"] = NSNull()
    }

    return (payload, featurePrint ?? previousFeaturePrint)
}

let options = parseArgs()

do {
    let entries = try readManifest(options.manifest)
    var output = ""
    var previousFeaturePrint: VNFeaturePrintObservation?
    var usableFrames = 0

    for entry in entries {
        let result = analyzeFrame(
            entry: entry,
            level: options.level,
            previousFeaturePrint: previousFeaturePrint
        )
        previousFeaturePrint = result.featurePrint
        if result.payload["error"] == nil {
            usableFrames += 1
        }
        output += jsonObject(result.payload)
        output += "\n"
    }

    if usableFrames == 0 {
        fputs("Apple Vision could not analyze any frames from \(options.manifest)\n", stderr)
        exit(1)
    }

    let outURL = URL(fileURLWithPath: options.out)
    try FileManager.default.createDirectory(
        at: outURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    try output.write(to: outURL, atomically: true, encoding: .utf8)
} catch {
    fputs("\(error.localizedDescription)\n", stderr)
    exit(1)
}
