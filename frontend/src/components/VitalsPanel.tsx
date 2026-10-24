"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import Link from "next/link";
import { api, VitalMetric, VitalSign } from "@/api";
import Icon from "@/components/Icon";

type BluetoothCharacteristicLike = EventTarget & {
  value: DataView | null;
  startNotifications(): Promise<BluetoothCharacteristicLike>;
};
type BluetoothServiceLike = {
  getCharacteristic(uuid: string): Promise<BluetoothCharacteristicLike>;
};
type BluetoothServerLike = {
  getPrimaryService(uuid: string): Promise<BluetoothServiceLike>;
};
type BluetoothDeviceLike = EventTarget & {
  name?: string;
  gatt?: {
    connect(): Promise<BluetoothServerLike>;
    disconnect(): void;
  };
};
type BluetoothManagerLike = {
  requestDevice(options: {
    filters?: { services: string[] }[];
    acceptAllDevices?: boolean;
    optionalServices: string[];
  }): Promise<BluetoothDeviceLike>;
};

const BLE_SERVICES = ["heart_rate", "health_thermometer", "pulse_oximeter"];
const METRICS: VitalMetric[] = ["heart_rate", "oxygen_saturation", "body_temperature"];
const LIMITS: Record<VitalMetric, { min: number; max: number; step: string }> = {
  heart_rate: { min: 20, max: 250, step: "1" },
  oxygen_saturation: { min: 40, max: 100, step: "0.1" },
  body_temperature: { min: 25, max: 45, step: "0.1" },
};
const UNITS: Record<VitalMetric, string> = {
  heart_rate: "bpm",
  oxygen_saturation: "%",
  body_temperature: "°C",
};
type LiveVital = {
  value: number;
  unit: string;
  source: "bluetooth" | "manual";
  device_name: string | null;
  captured_at: string;
};

function optionalService(server: BluetoothServerLike, id: string) {
  return server.getPrimaryService(id).catch((error: unknown) => {
    if (error instanceof DOMException && error.name === "NotFoundError") return null;
    throw error;
  });
}

function optionalCharacteristic(service: BluetoothServiceLike, id: string) {
  return service.getCharacteristic(id).catch((error: unknown) => {
    if (error instanceof DOMException && error.name === "NotFoundError") return null;
    throw error;
  });
}

function readSfloat(data: DataView, offset: number): number {
  const raw = data.getUint16(offset, true);
  let mantissa = raw & 0x0fff;
  if (mantissa & 0x0800) mantissa -= 0x1000;
  let exponent = raw >>> 12;
  if (exponent & 0x08) exponent -= 0x10;
  return mantissa * 10 ** exponent;
}

function readFloat(data: DataView, offset: number): number {
  let mantissa = data.getUint8(offset)
    | data.getUint8(offset + 1) << 8
    | data.getUint8(offset + 2) << 16;
  if (mantissa & 0x800000) mantissa -= 0x1000000;
  return mantissa * 10 ** data.getInt8(offset + 3);
}

function parseMeasurement(metric: VitalMetric, data: DataView): [VitalMetric, number][] {
  if (metric === "heart_rate") {
    if (data.byteLength < 2) return [];
    const bpm = data.getUint8(0) & 0x01
      ? data.byteLength >= 3 ? data.getUint16(1, true) : Number.NaN
      : data.getUint8(1);
    return Number.isFinite(bpm) ? [["heart_rate", bpm]] : [];
  }

  if (metric === "body_temperature") {
    if (data.byteLength < 5) return [];
    const temperature = readFloat(data, 1);
    const celsius = data.getUint8(0) & 0x01
      ? (temperature - 32) * 5 / 9
      : temperature;
    return Number.isFinite(celsius) ? [["body_temperature", celsius]] : [];
  }

  if (data.byteLength < 5) return [];
  const oxygen = readSfloat(data, 1);
  const bpm = readSfloat(data, 3);
  return [
    ...(Number.isFinite(oxygen) ? [["oxygen_saturation", oxygen] as [VitalMetric, number]] : []),
    ...(Number.isFinite(bpm) ? [["heart_rate", bpm] as [VitalMetric, number]] : []),
  ];
}

function rounded(metric: VitalMetric, value: number) {
  return metric === "heart_rate" ? Math.round(value) : Math.round(value * 10) / 10;
}

export default function VitalsPanel() {
  const { t, i18n } = useTranslation();
  const [readings, setReadings] = useState<VitalSign[]>([]);
  const [liveReadings, setLiveReadings] = useState<Partial<Record<VitalMetric, LiveVital>>>({});
  const [supported, setSupported] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectedName, setConnectedName] = useState("");
  const [error, setError] = useState("");
  const [metric, setMetric] = useState<VitalMetric>("heart_rate");
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const deviceRef = useRef<BluetoothDeviceLike | null>(null);
  const lastBluetoothSave = useRef<Record<VitalMetric, number>>({
    heart_rate: 0,
    oxygen_saturation: 0,
    body_temperature: 0,
  });
  const bluetoothSavesInFlight = useRef(new Set<VitalMetric>());

  const refresh = useCallback(async () => {
    try {
      setReadings(await api.vitals());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : t("wearables.loadError"));
    }
  }, [t]);

  useEffect(() => {
    setSupported(
      window.isSecureContext
      && "bluetooth" in navigator,
    );
    void refresh();
  }, [refresh]);

  useEffect(() => () => {
    deviceRef.current?.gatt?.disconnect();
  }, []);

  const saveReading = useCallback(async (
    kind: VitalMetric,
    rawValue: number,
    source: "bluetooth" | "manual",
    deviceName?: string,
  ): Promise<boolean> => {
    const nextValue = rounded(kind, rawValue);
    const capturedAt = new Date().toISOString();
    if (source === "bluetooth") {
      setLiveReadings((current) => ({
        ...current,
        [kind]: {
          value: nextValue,
          unit: UNITS[kind],
          source,
          device_name: deviceName ?? null,
          captured_at: capturedAt,
        },
      }));
      const now = Date.now();
      if (now - lastBluetoothSave.current[kind] < 60_000 || bluetoothSavesInFlight.current.has(kind)) return true;
      bluetoothSavesInFlight.current.add(kind);
    }

    try {
      const saved = await api.addVital({
        metric: kind,
        value: nextValue,
        source,
        ...(deviceName ? { device_name: deviceName } : {}),
        captured_at: capturedAt,
      });
      if (source === "bluetooth") lastBluetoothSave.current[kind] = Date.now();
      setReadings((current) => [saved, ...current.filter((item) => item.id !== saved.id)].slice(0, 30));
      setError("");
      return true;
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : t("wearables.saveError"));
      return false;
    } finally {
      if (source === "bluetooth") bluetoothSavesInFlight.current.delete(kind);
    }
  }, [t]);

  async function connectDevice() {
    setError("");
    setConnecting(true);
    try {
      const bluetooth = (navigator as Navigator & { bluetooth?: BluetoothManagerLike }).bluetooth;
      if (!bluetooth || !window.isSecureContext) {
        throw new Error(t("wearables.unsupported"));
      }

      const device = await bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: BLE_SERVICES,
      });
      deviceRef.current = device;
      device.addEventListener("gattserverdisconnected", () => {
        if (deviceRef.current === device) {
          deviceRef.current = null;
          setConnectedName("");
        }
      });

      if (!device.gatt) throw new Error(t("wearables.connectionError"));
      const server = await device.gatt.connect();
      const deviceName = device.name || t("wearables.unnamedDevice");
      let subscriptions = 0;

      const subscribe = async (serviceId: string, characteristicIds: string[], kind: VitalMetric) => {
        const service = await optionalService(server, serviceId);
        if (!service) return;

        let characteristic: BluetoothCharacteristicLike | null = null;
        for (const characteristicId of characteristicIds) {
          characteristic = await optionalCharacteristic(service, characteristicId);
          if (characteristic) break;
        }
        if (!characteristic) return;

        characteristic.addEventListener("characteristicvaluechanged", () => {
          const data = characteristic?.value;
          if (!data) return;
          for (const [nextMetric, nextValue] of parseMeasurement(kind, data)) {
            void saveReading(nextMetric, nextValue, "bluetooth", deviceName);
          }
        });
        await characteristic.startNotifications();
        subscriptions += 1;
      };

      await subscribe("heart_rate", ["heart_rate_measurement"], "heart_rate");
      await subscribe("health_thermometer", ["temperature_measurement"], "body_temperature");
      await subscribe(
        "pulse_oximeter",
        ["plx_continuous_measurement", "plx_spot_check_measurement"],
        "oxygen_saturation",
      );

      if (subscriptions === 0) {
        device.gatt.disconnect();
        deviceRef.current = null;
        throw new Error(t("wearables.noSupportedSensors"));
      }

      setConnectedName(deviceName);
    } catch (connectionError) {
      deviceRef.current?.gatt?.disconnect();
      deviceRef.current = null;
      setConnectedName("");
      setError(connectionError instanceof Error ? connectionError.message : t("wearables.connectionError"));
    } finally {
      setConnecting(false);
    }
  }

  async function submitManual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
      setError(t("wearables.invalidValue"));
      return;
    }

    setSaving(true);
    setError("");
    if (await saveReading(metric, numericValue, "manual")) setValue("");
    setSaving(false);
  }

  const latestByMetric = METRICS.map((kind) => {
    const saved = readings.find((reading) => reading.metric === kind);
    const live = liveReadings[kind];
    return live && (!saved || Date.parse(live.captured_at) >= Date.parse(saved.captured_at))
      ? live
      : saved;
  });
  const timestamp = (isoDate: string) => new Intl.DateTimeFormat(i18n.language, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(isoDate));

  return (
    <section className="card space-y-5 p-5 sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-brand-soft text-brand">
            <Icon name="heart" className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-lg font-semibold">{t("wearables.title")}</h2>
            <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">{t("wearables.description")}</p>
          </div>
        </div>
        {connectedName ? (
          <button type="button" onClick={() => deviceRef.current?.gatt?.disconnect()} className="btn btn-ghost">
            {t("wearables.disconnect")}
          </button>
        ) : (
          <button type="button" onClick={() => void connectDevice()} disabled={!supported || connecting} className="btn btn-primary">
            <Icon name="link" className="h-4 w-4" />
            {connecting ? t("wearables.connecting") : t("wearables.connect")}
          </button>
        )}
      </header>

      <p className="rounded-xl bg-surface-2 px-4 py-3 text-sm leading-6 text-muted">
        {connectedName
          ? t("wearables.connected", { name: connectedName })
          : supported ? t("wearables.bluetoothNote") : t("wearables.unsupported")}
      </p>

      <Link href="/assistant?ask=vitals" className="btn btn-soft w-fit">
        <Icon name="message" className="h-4 w-4" />{t("wearables.askLumi")}
      </Link>

      {error && <p role="alert" className="rounded-xl border border-crit/30 bg-crit-soft px-3 py-2 text-sm text-crit">{error}</p>}

      <div>
        <h3 className="mb-3 font-semibold">{t("wearables.latest")}</h3>
        <div className="grid gap-3 sm:grid-cols-3">
          {METRICS.map((kind, index) => {
            const reading = latestByMetric[index];
            return (
              <div key={kind} className="rounded-2xl border border-line bg-surface-2 p-4">
                <p className="text-sm text-muted">{t(`wearables.${kind}`)}</p>
                {reading ? (
                  <>
                    <p className="mt-2 text-2xl font-semibold tabular-nums text-ink">
                      {reading.value} <span className="text-sm font-medium text-muted">{reading.unit}</span>
                    </p>
                    <p className="mt-1 text-xs text-muted">{timestamp(reading.captured_at)}</p>
                    <p className="mt-1 truncate text-xs text-muted">
                      {t(reading.source === "bluetooth" ? "wearables.sourceBluetooth" : "wearables.sourceManual")}
                      {reading.device_name ? ` · ${reading.device_name}` : ""}
                    </p>
                  </>
                ) : <p className="mt-2 text-sm text-muted">{t("wearables.notRecorded")}</p>}
              </div>
            );
          })}
        </div>
      </div>

      <form onSubmit={(event) => void submitManual(event)} className="grid gap-3 border-t border-line pt-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <label className="block space-y-1.5 text-sm font-medium">
          {t("wearables.measurement")}
          <select value={metric} onChange={(event) => setMetric(event.target.value as VitalMetric)} className="input w-full">
            {METRICS.map((kind) => <option key={kind} value={kind}>{t(`wearables.${kind}`)}</option>)}
          </select>
        </label>
        <label className="block space-y-1.5 text-sm font-medium">
          {t("wearables.value")} ({UNITS[metric]})
          <input
            className="input w-full"
            type="number"
            min={LIMITS[metric].min}
            max={LIMITS[metric].max}
            step={LIMITS[metric].step}
            required
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
        <button type="submit" className="btn btn-ghost border border-line" disabled={saving}>
          {saving ? t("wearables.saving") : t("wearables.save")}
        </button>
      </form>

      <p className="text-xs leading-5 text-muted">{t("wearables.safetyNote")}</p>
    </section>
  );
}

