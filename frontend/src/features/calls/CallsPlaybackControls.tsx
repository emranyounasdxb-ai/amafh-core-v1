import { useEffect, useState, type RefObject } from "react";
import { Button, DsIcon } from "../../design-system";
import { playbackTime } from "./callsPresentation";

export function CallsPlaybackControls({
  audioRef,
  recordingId,
  playing,
  busy,
  onToggle,
}: {
  audioRef: RefObject<HTMLAudioElement | null>;
  recordingId: string;
  playing: boolean;
  busy: boolean;
  onToggle: () => void;
}) {
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [speed, setSpeed] = useState("1");

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const update = () => {
      setPosition(Number.isFinite(audio.currentTime) ? audio.currentTime : 0);
      setDuration(Number.isFinite(audio.duration) ? audio.duration : 0);
    };
    const events = [
      "timeupdate",
      "durationchange",
      "loadedmetadata",
      "emptied",
      "seeked",
    ];
    events.forEach((event) => audio.addEventListener(event, update));
    update();
    return () =>
      events.forEach((event) => audio.removeEventListener(event, update));
  }, [audioRef, recordingId]);

  function seek(seconds: number) {
    const audio = audioRef.current;
    if (!audio || duration <= 0) return;
    audio.currentTime = Math.max(0, Math.min(seconds, duration));
    setPosition(audio.currentTime);
  }

  return (
    <div className="calls-playback-controls">
      <input
        className="calls-seek"
        aria-label="Recording position"
        type="range"
        min="0"
        max={duration || 1}
        step="0.1"
        value={Math.min(position, duration || 1)}
        disabled={!duration}
        onChange={(event) => seek(Number(event.target.value))}
        aria-valuetext={`${playbackTime(position)} of ${playbackTime(duration)}`}
      />
      <div className="calls-playback-times">
        <span>{playbackTime(position)}</span>
        <span>{duration ? playbackTime(duration) : "—:—"}</span>
      </div>
      <div className="calls-transport">
        <Button
          variant="ghost"
          aria-label="Rewind 10 seconds"
          disabled={!duration}
          onClick={() => seek(position - 10)}
        >
          <DsIcon name="rewind10" size={20} />
          <span className="calls-skip-count" aria-hidden="true">
            10
          </span>
        </Button>
        <Button
          className="calls-main-play"
          aria-label={playing ? "Pause recording" : "Play recording"}
          disabled={!recordingId || (busy && !playing)}
          onClick={onToggle}
        >
          <DsIcon name={playing ? "pause" : "play"} size={24} />
        </Button>
        <Button
          variant="ghost"
          aria-label="Forward 10 seconds"
          disabled={!duration}
          onClick={() => seek(position + 10)}
        >
          <DsIcon name="forward10" size={20} />
          <span className="calls-skip-count" aria-hidden="true">
            10
          </span>
        </Button>
      </div>
      <div className="calls-playback-settings">
        <label>
          Speed
          <select
            aria-label="Playback speed"
            value={speed}
            onChange={(event) => {
              setSpeed(event.target.value);
              if (audioRef.current) {
                audioRef.current.defaultPlaybackRate = Number(
                  event.target.value,
                );
                audioRef.current.playbackRate = Number(event.target.value);
              }
            }}
          >
            {["0.75", "1", "1.25", "1.5", "2"].map((value) => (
              <option key={value} value={value}>
                {value}×
              </option>
            ))}
          </select>
        </label>
        <label className="calls-volume">
          <DsIcon name="volume" size={16} />
          <span className="ds-sr-only">Volume</span>
          <input
            aria-label="Volume"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={volume}
            onChange={(event) => {
              const next = Number(event.target.value);
              setVolume(next);
              if (audioRef.current) audioRef.current.volume = next;
            }}
          />
        </label>
      </div>
    </div>
  );
}
