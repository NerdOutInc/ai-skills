#!/usr/bin/env swift
import CoreGraphics
import Foundation

let args = CommandLine.arguments

func usage() -> Never {
  fputs("""
  usage:
    scroll-wheel.swift <repeats> <wheel1-delta> <delay-seconds> [wheel2-delta]
    scroll-wheel.swift trackpad <bursts> <up|down> <delay-seconds> <pause-seconds> [deltas]

  deltas is a comma-separated acceleration curve, defaulting to 4,8,14,22,30,22,14,8,4.

  """, stderr)
  exit(64)
}

let source = CGEventSource(stateID: .hidSystemState)

func postScroll(_ wheel1: Int32) {
  if let event = CGEvent(
    scrollWheelEvent2Source: source,
    units: .pixel,
    wheelCount: 2,
    wheel1: wheel1,
    wheel2: 0,
    wheel3: 0
  ) {
    event.post(tap: .cghidEventTap)
  }
}

if args.count >= 6 && args[1] == "trackpad" {
  guard let bursts = Int(args[2]),
        let delay = Double(args[4]),
        let pause = Double(args[5]) else {
    usage()
  }

  let direction = args[3].lowercased()
  let sign: Int32
  switch direction {
  case "up":
    sign = 1
  case "down":
    sign = -1
  default:
    usage()
  }

  let curveText = args.count >= 7 ? args[6] : "4,8,14,22,30,22,14,8,4"
  let curve = curveText.split(separator: ",").compactMap { Int32($0.trimmingCharacters(in: .whitespaces)) }
  guard !curve.isEmpty else {
    usage()
  }

  for burstIndex in 0..<bursts {
    for delta in curve {
      postScroll(sign * delta)
      Thread.sleep(forTimeInterval: delay)
    }
    if burstIndex < bursts - 1 {
      Thread.sleep(forTimeInterval: pause)
    }
  }
  exit(0)
}

guard args.count >= 4,
      let repeats = Int(args[1]),
      let wheel1 = Int32(args[2]),
      let delay = Double(args[3]) else {
  usage()
}

let wheel2 = args.count >= 5 ? (Int32(args[4]) ?? 0) : 0

for _ in 0..<repeats {
  if let event = CGEvent(
    scrollWheelEvent2Source: source,
    units: .pixel,
    wheelCount: 2,
    wheel1: wheel1,
    wheel2: wheel2,
    wheel3: 0
  ) {
    event.post(tap: .cghidEventTap)
  }
  Thread.sleep(forTimeInterval: delay)
}
