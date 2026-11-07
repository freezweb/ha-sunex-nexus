"""Generate matching EN/DE translations and original integration brand assets."""
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/sunex_nexus"
LABELS = {
    "sensor": {
        "water_inlet_temperature": ("Water inlet", "Wassereinlass"),
        "water_outlet_temperature": ("Water outlet", "Wasserauslass"),
        "tank_temperature": ("Tank temperature", "Speichertemperatur"),
        "ambient_temperature": ("Outdoor temperature", "Aussentemperatur"),
        "return_gas_temperature": ("Suction gas temperature", "Sauggastemperatur"),
        "outdoor_coil_temperature": ("Evaporator temperature", "Verdampfertemperatur"),
        "cooling_coil_temperature": ("Cooling coil temperature", "Kuehlwaermetauscher"),
        "discharge_gas_temperature": ("Discharge gas temperature", "Heissgastemperatur"),
        "main_expansion_valve": ("Main expansion valve raw", "Haupt-Expansionsventil Rohwert"),
        "auxiliary_expansion_valve": ("Auxiliary expansion valve raw", "Hilfs-Expansionsventil Rohwert"),
        "compressor_frequency": ("Compressor frequency", "Verdichterfrequenz"),
        "dc_bus_voltage": ("DC bus voltage", "Zwischenkreisspannung"),
        "target_frequency": ("Target compressor frequency", "Verdichter-Sollfrequenz"),
        "fan_1_speed": ("Fan 1 speed", "Luefter 1 Drehzahl"),
        "dc_pump_speed_raw": ("DC pump speed raw", "DC-Pumpendrehzahl Rohwert"),
        "faults": ("Active fault count", "Aktive Fehleranzahl"),
    },
    "binary_sensor": {
        "enabled": ("Unit enabled", "Geraet freigegeben"),
        "compressor_running": ("Compressor running", "Verdichter laeuft"),
        "fan_running": ("Fan running", "Luefter laeuft"),
        "pump_running": ("Water pump running", "Wasserpumpe laeuft"),
        "defrost": ("Defrost", "Abtauung"),
        "flow_switch_closed": ("Flow switch closed", "Stroemungskontakt geschlossen"),
        "evu_contact_closed": ("EVU contact closed", "EVU-Kontakt geschlossen"),
        "sg_contact_closed": ("SG contact closed", "SG-Kontakt geschlossen"),
        "write_lock": ("Uncertain command lock", "Schreibsperre nach unbestaetigtem Befehl"),
    },
    "number": {
        "heating_setpoint": ("Heating inlet target", "Heizen Einlass-Solltemperatur"),
        "cooling_setpoint": ("Cooling inlet target", "Kuehlen Einlass-Solltemperatur"),
        "hot_water_setpoint": ("Hot water target", "Warmwasser-Solltemperatur"),
    },
    "switch": {
        "enabled": ("Unit enable", "Geraetefreigabe"),
        "powerful": ("Powerful mode", "Leistungsbetrieb"),
        "silent": ("Silent mode", "Leisebetrieb"),
        "weather_compensation": ("Weather compensation", "Heizkompensation"),
        "holiday": ("Holiday mode", "Urlaubsbetrieb"),
        "service_edit": ("Service editing (10 minutes)", "Servicebearbeitung (10 Minuten)"),
    },
    "button": {"acknowledge_write_lock": ("Acknowledge command after inspection", "Befehl nach Pruefung quittieren")},
    "select": {"mode": ("Operating mode", "Betriebsart")},
}


def translations(language):
    de = language == "de"
    entities = {platform: {key: {"name": pair[int(de)]} for key, pair in rows.items()}
                for platform, rows in LABELS.items()}
    entities["select"]["mode"]["state"] = dict(zip(
        ["hot_water", "heating", "cooling", "hot_water_heating", "hot_water_cooling"],
        ["Warmwasser", "Heizen", "Kuehlen", "Warmwasser und Heizen", "Warmwasser und Kuehlen"] if de else
        ["Hot water", "Heating", "Cooling", "Hot water and heating", "Hot water and cooling"]))
    return {
        "title": "SUNEX NEXUS",
        "config": {
            "step": {"user": {
                "title": "SUNEX NEXUS M-EVI",
                "description": (
                    "Lokales RTU-over-TCP-Gateway, 9600 Baud, 8N1, Geraeteadresse 1. Nur fuer bestaetigte M-EVI-Registerkarten. Kein anderer Modbus-Master darf dieses Gateway oder denselben Bus verwenden. Einrichtung liest nur; Schreibzugriffe bleiben aus."
                    if de else "Local RTU-over-TCP gateway, 9600 baud, 8N1, slave 1. Only for confirmed M-EVI register maps. No other Modbus master may use this gateway or bus. Setup only reads; writes remain disabled."),
                "data": {"host": "Host", "port": "Port", "exclusive_gateway":
                    "Ich habe die exklusive Busnutzung und M-EVI-Kompatibilitaet geprueft" if de else
                    "I verified exclusive bus ownership and M-EVI compatibility"}}},
            "error": {"cannot_connect": "Gateway nicht erreichbar oder Registerkarte nicht kompatibel" if de else
                      "Cannot connect or unsupported register map",
                      "exclusive_required": "Exklusive Busnutzung muss bestaetigt werden" if de else
                      "Exclusive bus ownership must be confirmed"},
            "abort": {"already_configured": "Dieses Gateway ist bereits eingerichtet" if de else
                      "This gateway is already configured"},
        },
        "options": {"step": {"init": {
            "title": "Kommunikation und Schreibzugriff" if de else "Communication and write access",
            "description": "Schreiben nur fuer beaufsichtigte, korrekt angeschlossene Anlagen aktivieren. Keine Schutzfunktionen ueberbruecken. Serviceparameter benoetigen zusaetzlich Geraet und Verdichter aus sowie die 10-Minuten-Freigabe." if de else
            "Enable writes only for supervised, correctly connected installations. Do not bypass protections. Service parameters additionally require unit and compressor off and the 10-minute service switch.",
            "data": {"allow_writes": "Schreibzugriffe erlauben" if de else "Allow writes",
                     "poll_interval": "Abfrageintervall (Sekunden)" if de else "Polling interval (seconds)"},
        }}},
        "entity": entities,
    }


def png(size):
    """An original geometric airflow/heat mark, not a SUNEX or HA trademark."""
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            u, v = x / size, y / size
            ring = 0.26 < ((u - .5)**2 + (v - .5)**2)**.5 < .49
            bars = any(abs(v - center) < .035 and .23 < u < .77 for center in (.35, .5, .65))
            row.extend((0, 137, 139, 255) if ring else ((222, 68, 63, 255) if bars else (0, 0, 0, 0)))
        rows.append(b"\x00" + row)
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    (COMPONENT / "translations").mkdir(exist_ok=True)
    for language in ("en", "de"):
        text = json.dumps(translations(language), indent=2, ensure_ascii=True) + "\n"
        (COMPONENT / "translations" / f"{language}.json").write_text(text, encoding="utf-8")
        if language == "en":
            (COMPONENT / "strings.json").write_text(text, encoding="utf-8")
    (COMPONENT / "brand").mkdir(exist_ok=True)
    for filename, size in (("icon.png", 256), ("icon@2x.png", 512)):
        (COMPONENT / "brand" / filename).write_bytes(png(size))
