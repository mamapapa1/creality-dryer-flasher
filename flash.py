#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Creality Space Pi X4 Lite — self-contained firmware flasher (GD32F303CBT6).
All firmware images are embedded in this file.

Backend: pyOCD (pip install pyocd, default) or OpenOCD (--backend openocd).

SAFETY: connecting the debugger under 220 V mains is NOT recommended unless
galvanic isolation is confirmed. Safe path: power the board from 5 V USB only.

No arguments — interactive mode: language -> firmware -> (90 C only) calibration.
  python3 flash.py
CLI:
  python3 flash.py --lang en --firmware mod90c --calibrate 11
  python3 flash.py --firmware stock            # revert to factory
  python3 flash.py --build-only out.bin        # build .bin without flashing
  python3 flash.py --dump backup.bin           # back up current firmware
"""

import argparse
import atexit
import base64
import gzip
import hashlib
import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import tempfile

# --- constants ---------------------------------------------------------------

FLASH_BASE = 0x08000000
FLASH_SIZE = 128 * 1024

# Calibration: T = raw*K - C1, where C1 is a float32 at CAL_ADDR (factory 50.0).
# Adding +X C to readings  <=>  C1 = 50.0 - X.
CAL_ADDR = 0x0A94
CAL_BASE = 50.0
CAL_LIMIT = 30.0
CAL_RECOMMENDED = 11.0   # nonlinear sensor; +11 makes display match reality at ~90 C

PYOCD_TARGET = "gd32f303cb"
PYOCD_PACK = "gd32f303cb"
TARGET_CFG = "target/stm32f3x.cfg"
INTERFACE_CFG = {
    "stlink": "interface/stlink.cfg",
    "cmsis-dap": "interface/cmsis-dap.cfg",
    "jlink": "interface/jlink.cfg",
}

# Firmware metadata: key -> (expected sha256, i18n description key)
FW_META = {
    "mod90c": ("a85fb69db057fd636811ad952987033ee8be582970002235972d39340bf7b23c", "fw_mod90"),
    "stock":  ("eaf47944c9102b2e1ff658e3824a0d5f3b94e74d69927b4cb3a9d7d6a2aff69e", "fw_stock"),
}
# Calibration is offered only for the 90 C mod (not for revert).
CALIBRATABLE = ("mod90c",)

# Embedded firmware: key -> base64(gzip(bin)). Generated automatically.
_FW_BLOBS = {
    "mod90c": (
        "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"
        "Cbn+IG55YxcNyA8Vu8WXoAh12f+nffmhw/7ebqlU+m3GpYkQXeo9NA0Sb2z9zCgVY0hB/CqJLh26FEtB9O0l6avPkdTWbx+d"
        "EmOHMDyoOG+p+J41JpsgiXwsiemAJDE9sDSuizRWBstitEh2/f9BSmTf98fcgGNuwDH/HReN9vb2RmGljZK/lAG4aDT8M1zs"
        "75dwsb8U8rD9HDfyF3BTfwG38Rdw0V/D/f0XcD9Ff/VPClWlwdoz7i5ARsvdyPeQ2BTscrDtNoxo10pELyfn6AqELkAaj1OX"
        "TJhEjc6n5mPlEyUTbq3KHjec3SdNs+BU8YegJzI6+j6Wvs9AL3Kn7XloOP2hFBdmONbesVz24Ey1263L0CXcS+Hx6hHjktSv"
        "P69Q7+5OVO9Ynaj+O0+rv32YVg+S0urUnQnqlRMT1AeOy9XPueTql3Lk6g3NMvXlzTL1xwaZenmPVP1jvVTdXilVl1ql6sY0"
        "qTrnvERd6JGou56QqLPulai36SVqjUKiPvQfSm34glJXv0WpdzxBqcc/QKlLSij18Zsp9d4hlPr7XqwefwGr3zmO1TcdxurP"
        "3sfq23didc3TWH1+HVaHlmL1n+/B6tkWrH5+MlavGY/V7SxWKwZj9ceJOOdUb84T7TnvBXLuPJ9jOJnz4d9z1v81Z7c3R3sg"
        "B3ty8t7PqXk75/4/5Cx6OWfP9pxx23Lans75oXL44McmZbtyktfmNP0/7d3Ba9d1GAfw7899Nn9qzs1tbvt8c27fZyrNDHMz"
        "f+VMZRbSsAQlVJBGKJqmu3Xo1ik8iCRdwiF16NgholCxQxKEXhIZIgSdPFuINlPTtv4CTx3k9To9z+U5vOF5rs9kXD4Wvx+O"
        "6mCcmoi+A+X1fY3q3Ti3u/xuV6PaWb4yvrfaEYNvxk9j8dG2ctuWRrU5ejbFwKvx+sb4cEN8MxyPX4731sWvL8Xba8vf1oxU"
        "Q+XyFyaq1XFmVRxYWY4Mfr4+qiru9cfdFfGwLy9KMbi83P78nqosp3Kj6s1tqdzdM1V1l7eX9fem+LIrz0txpLOc7uicbS8s"
        "zcOp/La9Ple35bEU15bk91PMtObTKQ+luLI4H0t5SYofnssTKS9OcWlRPpFyleLmwvxZyuMp11P8siB/mvJbKbemmK7nsykf"
        "Snldikfz89WUv0j5aMqj/8251ZIvpvYXa3NPGP7sOF9LY7MH+rUHtdrSjnpb77zu2YU8Vzu/oP2D4x+nB6mxsKvlZHPX/q+b"
        "PylbV98YmFu/77f+VWz9+U6teOdOUftn5o/7f89selL8+AQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADgf1I8BSkBAAAAAAA8u4qic7Sp"
        "s1g/2tRTvHHzq0mJAMCz7184nuRGAAACAA=="
    ),
    "stock": (
        "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"
        "p49xsGmNLbBYqQyWKndAP7QFSpVfh5BMkidah6KCx1fPgZZJF1tmqCyHx9SWDFLe9wO6efDpZVZ6AWkNeg6lTWzemkWxs5zZ"
        "hczaqizSZhjCPdDfiOzd/vmijlPb931cmWV1agorocdWZhGar/0a831g2VDXelNItO1RL7EO2PXmoeKdlZSurfz/ybpyaEP5"
        "qCd/mGwxOZlh0Af0aGym95ygbHig6Ji3tigDuNlEbtROcicH+GXEbv/E5r/r+cX6xCKo56TTo6ywKovrg9pLNMZjN7aXfby3"
        "aGN49sdUsJCqi1v2LYjJjDw1bPx4mkkSbF4zj5EECySkDy5AP+9z6cA/HfpcE0feytIZUBaNAml3nEucNmwBee85bA6lkzdj"
        "DV67M1MSHwdUvI8yP8TmIpNt7qglk9k1ziVLHylfz65c9YhGQw78Rj4VnPn+tfzVzjVL+zPjuCVLFy93rryGRnKrYgHKm9r+"
        "r4/IbELqWSXOJaf/E5M1pITZN9tJ1sCM9B3CfENqCR6X6qSCBmpYk6fj/MYhpxnx7m2qP30F0krOJvvnQpx0rux5Q6a7rmzz"
        "FK3G+5YwuQGzzCGuGPsJzByK3Qsm/EmcbtHvw450C8rZLoxlDc4hpTYeK3Gewpft2t45iZmT9UdYh9zCfQ2Sc1tN+CxA+mRr"
        "ooNQ47xBvkUi1d1Zu0z/AKp5DeS98VbTUS+JIa0n8ZT4We7R/jMyqRk5Uq2VEcRuYsj7QbuddUBKsxVS5yus4upFvB52td+R"
        "7SBn3EeCRrxlxCBdvpctlzSz5p6wtpd1+u3k/I3ct+GKyQ4C86O6Hmcx/+9OzO/oJDsdcuZ3DlLPdJK3USg3yTdYwEmYbwZc"
        "JTl995F9g3rclWbM39IFNondL15494wJrkKdeHb+yLExNp5SlFnLpuPcRBdpD6KfLWBMPHFRmkppx/imTcPavZ3IXTxtuEsS"
        "fEIyxnfMsYofk5wcLEj2CfbaK0WTTivXvSVo3QnBAlT9ZKXwmwYcGoK+dHgEO6OoQxrS/1hyGqzrbB7lrwSf55j4XoJ56i0h"
        "tzrT/78vLRdLXyvrcL7ZlqtwQ//Bz+KnG5+qfGrTtpkZmKznDW7wDqDvNZA1nfg7OueXDsXKCeKZb13QmLIP2tRsgNAAqzaE"
        "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"
    ),
}

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RST = "\033[0m"

# --- localization ------------------------------------------------------------

LANG_ORDER = [("ru", "Русский"), ("en", "English"), ("de", "Deutsch"), ("es", "Español"), ("zh", "中文")]
_LANG = "ru"

LANGS = {
    "ru": {
        "banner": "Прошивка сушилки Creality Space Pi X4 Lite",
        "what_to_flash": "Что прошить? (цифра и Enter)",
        "fw_mod90": "90 °C / 194 °F (поднять максимум)",
        "fw_stock": "Откат на заводскую (75 °C / 167 °F)",
        "exit": "выход",
        "choice_prompt": "Выбор [1-{n}, Enter=1, 0={exit}]: ",
        "chosen": "Выбрано: {name}",
        "press_digit": "  Нужна цифра из списка.",
        "calib_header": "Калибровка температуры:",
        "calib_l1": "  При нагреве дисплей занижает t — рекомендуется +{rec:.0f} °C (+{rec_f:.0f} °F): тогда на 90 °C показания совпадут с реальной.",
        "calib_l2": "  Свой замер: термометр в переднее отверстие для PTFE-трубки, смещение = термометр − дисплей.",
        "calib_prompt": "Смещение, °C [Enter=+{rec:.0f} / 0 = без / напр. 9.5 или -3]: ",
        "need_number": "  Нужно число (например 10 или 0).",
        "calib_applied": "[i] Калибровка: {off:+.1f} °C  (C1 {base:.0f} → {new:.1f})",
        "calib_limit": "[!] Смещение {off:+.1f} °C вне предела ±{lim:.0f} — стоит перепроверить измерения.",
        "calib_already": "[!] В прошивке C1={cur:.3f}, не {base:.0f} — смещение отсчитывается от {base:.0f}.",
        "backend_line": "[i] Бэкенд: {b}",
        "fw_line": "[i] Прошивка: {name}",
        "size_line": "    размер  : {size} байт",
        "sha_line": "    sha256  : {sha}",
        "size_warn": "[!] Ожидался размер {exp} байт, а получилось {size}.",
        "safety": ("\n⚠  БЕЗОПАСНОСТЬ  ⚠\n"
                   "  Подключать отладчик к ПК при поданных 220 В НЕ рекомендуется\n"
                   "  (без подтверждённой развязки — см. README).\n"
                   "  Безопасно — при питании платы от 5 В USB.\n"
                   "  Линии: SWDIO · SWCLK · GND (+ 3.3V/5V при необходимости)."),
        "safety_prompt": "220 В снято, отладчик подключён? Прошивка —  1=да  0=отмена: ",
        "yes_skip": "[i] --yes: подтверждение пропущено.",
        "cancelled": "Отменено.",
        "success": "\n[✓] Прошивка залита и проверена. Готово.",
        "disconnect_warn": "    Перед подачей 220 В на плату отладчик нужно отключить.",
        "calib_after": "    Калибровка {off:+.1f} °C вписана. Стоит сверить термометром; при необходимости — перепрошивка с уточнённым числом.",
        "err_backend": "\n[✗] {b} завершился с кодом {rc}.",
        "err_hints": "    Частые причины: отладчик не воткнут / не та скорость / нет драйвера.\n    Помогает --speed 300 (или 200) и питание платы от 5 В USB.",
        "err_win": "    Windows + ST-Link: нужен WinUSB-драйвер (через Zadig).",
        "pyocd_missing": ("[!] pyOCD не установлен. Ставится одной командой:\n"
                          "      pip install pyocd\n"
                          "    Пак для GD32 флэшер поставит сам. (Или: OpenOCD + --backend openocd.)"),
        "openocd_missing": ("[!] OpenOCD не найден. Нужно установить его или использовать pyOCD:\n"
                            "      pip install pyocd"),
        "no_tool": "[!] Не найден ни pyOCD, ни OpenOCD.\n    Рекомендуется:  pip install pyocd",
        "pack_installing": "[i] Ставлю CMSIS-пак для {t} (один раз, нужен интернет)...",
        "pack_fail": "[!] Не удалось поставить пак. Вручную:  pyocd pack install {pack}",
        "build_done": "\n[✓] Собрано без прошивки: {out}",
        "plate_untouched": "    Плата не затронута — файл можно проверить/сравнить.",
        "dump_saved": "\n[✓] Бэкап сохранён: {out}",
        "dump_fail": "\n[✗] Не удалось снять дамп (код {rc}).",
        "fw_not_found": "[!] Прошивка не найдена: {key}",
        "list_header": "\nДоступные прошивки:",
        "sha_mismatch": "[!] Контрольная сумма зашитой прошивки {key} не совпала.",
        "cmd_label": "\n[+] Команда {b}:",
        "wiring": ("\nПодключение ST-Link → плата (SWD):\n"
                   "   SWDIO  (DIO)   →  SWDIO\n"
                   "   SWCLK  (CLK)   →  SWCLK\n"
                   "   GND            →  GND\n"
                   "   3.3V           →  шина 3.3 В платы (VDD MCU) — питает чип\n"
                   "   RST            →  не подключать\n"
                   "Питание — 3.3 В от ST-Link, 220 В не нужно. Дисплей на столе не горит (норма)."),
        "verify_start": "[i] Проверка: читаю прошивку обратно с платы...",
        "verify_ok": "[✓] Проверка пройдена: прошивка на плате совпадает байт-в-байт.",
        "verify_fail": "[✗] Проверка НЕ пройдена: прочитанное не совпало — нужна перепрошивка.",
        "press_enter_exit": "Enter — закрыть окно.",
        "offer_install": "pyOCD не найден. Установить сейчас (pip install pyocd)? [Y/n]: ",
        "installing_pyocd": "[i] Установка pyOCD (нужен интернет)...",
        "install_failed": "[!] Не удалось установить pyOCD. Вручную: pip install pyocd",
    },
    "en": {
        "banner": "Creality Space Pi X4 Lite dryer flasher",
        "what_to_flash": "What to flash? (press a number and Enter)",
        "fw_mod90": "90 °C / 194 °F (raise the max)",
        "fw_stock": "Revert to factory (75 °C / 167 °F)",
        "exit": "exit",
        "choice_prompt": "Choice [1-{n}, Enter=1, 0={exit}]: ",
        "chosen": "Selected: {name}",
        "press_digit": "  Press a number from the list.",
        "calib_header": "Temperature calibration:",
        "calib_l1": "  On heating the display reads low — recommended +{rec:.0f} °C (+{rec_f:.0f} °F): then 90 °C reads correctly.",
        "calib_l2": "  Your own value: thermometer in the front PTFE-tube hole, offset = thermometer − display.",
        "calib_prompt": "Offset, °C [Enter=+{rec:.0f} / 0 = none / e.g. 9.5 or -3]: ",
        "need_number": "  Enter a number (e.g. 10 or 0).",
        "calib_applied": "[i] Calibration: {off:+.1f} °C  (C1 {base:.0f} → {new:.1f})",
        "calib_limit": "[!] Offset {off:+.1f} °C is out of the ±{lim:.0f} range. Check your readings.",
        "calib_already": "[!] Firmware C1={cur:.3f}, not {base:.0f} — offset is taken from {base:.0f}.",
        "backend_line": "[i] Backend: {b}",
        "fw_line": "[i] Firmware: {name}",
        "size_line": "    size    : {size} bytes",
        "sha_line": "    sha256  : {sha}",
        "size_warn": "[!] Expected {exp} bytes, got {size}.",
        "safety": ("\n⚠  SAFETY  ⚠\n"
                   "  Connecting the debugger under 220 V mains is NOT recommended\n"
                   "  (unless isolation is confirmed — see README).\n"
                   "  Safe way: power the board from 5 V USB.\n"
                   "  Lines: SWDIO · SWCLK · GND (+ 3.3V/5V if needed)."),
        "safety_prompt": "Mains 220 V off, debugger connected? Flash —  1=yes  0=cancel: ",
        "yes_skip": "[i] --yes: confirmation skipped.",
        "cancelled": "Cancelled.",
        "success": "\n[✓] Firmware written and verified. Done.",
        "disconnect_warn": "    Disconnect the debugger before applying 220 V to the board.",
        "calib_after": "    Calibration {off:+.1f} °C applied. Verify with a thermometer; reflash with a refined value if needed.",
        "err_backend": "\n[✗] {b} exited with code {rc}.",
        "err_hints": "    Common causes: probe not plugged / wrong speed / missing driver.\n    Try --speed 300 (or 200) and 5 V USB power to the board.",
        "err_win": "    Windows + ST-Link: install the WinUSB driver via Zadig.",
        "pyocd_missing": ("[!] pyOCD is not installed. Install with one command:\n"
                          "      pip install pyocd\n"
                          "    The GD32 pack is installed automatically. (Or: OpenOCD + --backend openocd.)"),
        "openocd_missing": ("[!] OpenOCD not found. Install it or use pyOCD:\n"
                            "      pip install pyocd"),
        "no_tool": "[!] Neither pyOCD nor OpenOCD found.\n    Recommended:  pip install pyocd",
        "pack_installing": "[i] Installing the CMSIS pack for {t} (once, needs internet)...",
        "pack_fail": "[!] Failed to install the pack. Manually:  pyocd pack install {pack}",
        "build_done": "\n[✓] Built without flashing: {out}",
        "plate_untouched": "    The board was not touched — you can inspect/compare the file.",
        "dump_saved": "\n[✓] Backup saved: {out}",
        "dump_fail": "\n[✗] Failed to dump (code {rc}).",
        "fw_not_found": "[!] Firmware not found: {key}",
        "list_header": "\nAvailable firmware:",
        "sha_mismatch": "[!] Embedded firmware {key} checksum mismatch.",
        "cmd_label": "\n[+] {b} command:",
        "wiring": ("\nST-Link → board (SWD) wiring:\n"
                   "   SWDIO  (DIO)   →  SWDIO\n"
                   "   SWCLK  (CLK)   →  SWCLK\n"
                   "   GND            →  GND\n"
                   "   3.3V           →  board 3.3 V rail (MCU VDD) — powers the chip\n"
                   "   RST            →  leave unconnected\n"
                   "Powered from ST-Link 3.3 V, no mains. Display stays dark on the bench (normal)."),
        "verify_start": "[i] Verifying: reading firmware back from the board...",
        "verify_ok": "[✓] Verification passed: on-board firmware matches byte-for-byte.",
        "verify_fail": "[✗] Verification FAILED: readback mismatch — re-flash.",
        "press_enter_exit": "Press Enter to close.",
        "offer_install": "pyOCD not found. Install now (pip install pyocd)? [Y/n]: ",
        "installing_pyocd": "[i] Installing pyOCD (needs internet)...",
        "install_failed": "[!] Failed to install pyOCD. Manually: pip install pyocd",
    },
    "de": {
        "banner": "Creality Space Pi X4 Lite Trockner-Flasher",
        "what_to_flash": "Was flashen? (Zahl drücken und Enter)",
        "fw_mod90": "90 °C / 194 °F (Maximum anheben)",
        "fw_stock": "Zurück auf Werk (75 °C / 167 °F)",
        "exit": "Beenden",
        "choice_prompt": "Auswahl [1-{n}, Enter=1, 0={exit}]: ",
        "chosen": "Gewählt: {name}",
        "press_digit": "  Bitte eine Zahl aus der Liste.",
        "calib_header": "Temperaturkalibrierung:",
        "calib_l1": "  Beim Heizen zeigt die Anzeige zu niedrig — empfohlen +{rec:.0f} °C (+{rec_f:.0f} °F): dann stimmt 90 °C.",
        "calib_l2": "  Eigener Wert: Thermometer in die vordere PTFE-Öffnung, Offset = Thermometer − Anzeige.",
        "calib_prompt": "Offset, °C [Enter=+{rec:.0f} / 0 = keine / z.B. 9.5 oder -3]: ",
        "need_number": "  Bitte eine Zahl (z.B. 10 oder 0).",
        "calib_applied": "[i] Kalibrierung: {off:+.1f} °C  (C1 {base:.0f} → {new:.1f})",
        "calib_limit": "[!] Offset {off:+.1f} °C außerhalb ±{lim:.0f}. Messungen prüfen.",
        "calib_already": "[!] Firmware C1={cur:.3f}, nicht {base:.0f} — Offset wird ab {base:.0f} gerechnet.",
        "backend_line": "[i] Backend: {b}",
        "fw_line": "[i] Firmware: {name}",
        "size_line": "    Größe   : {size} Bytes",
        "sha_line": "    sha256  : {sha}",
        "size_warn": "[!] Erwartet {exp} Bytes, erhalten {size}.",
        "safety": ("\n⚠  SICHERHEIT  ⚠\n"
                   "  Debugger bei anliegenden 220 V anzuschließen ist NICHT empfohlen\n"
                   "  (ohne bestätigte Trennung — siehe README).\n"
                   "  Sicher: Platine über 5 V USB versorgen.\n"
                   "  Leitungen: SWDIO · SWCLK · GND (+ 3.3V/5V bei Bedarf)."),
        "safety_prompt": "220 V getrennt, Debugger verbunden? Flashen —  1=ja  0=abbrechen: ",
        "yes_skip": "[i] --yes: Bestätigung übersprungen.",
        "cancelled": "Abgebrochen.",
        "success": "\n[✓] Firmware geschrieben und verifiziert. Fertig.",
        "disconnect_warn": "    Debugger trennen, bevor 220 V an die Platine kommen.",
        "calib_after": "    Kalibrierung {off:+.1f} °C eingetragen. Mit Thermometer prüfen, ggf. mit genauerem Wert neu flashen.",
        "err_backend": "\n[✗] {b} endete mit Code {rc}.",
        "err_hints": "    Häufige Ursachen: Probe nicht gesteckt / falsche Geschwindigkeit / Treiber fehlt.\n    Versuchen Sie --speed 300 (oder 200) und 5 V USB-Versorgung.",
        "err_win": "    Windows + ST-Link: WinUSB-Treiber via Zadig installieren.",
        "pyocd_missing": ("[!] pyOCD ist nicht installiert. Mit einem Befehl installieren:\n"
                          "      pip install pyocd\n"
                          "    Das GD32-Pack wird automatisch installiert. (Oder: OpenOCD + --backend openocd.)"),
        "openocd_missing": ("[!] OpenOCD nicht gefunden. Installieren oder pyOCD nutzen:\n"
                            "      pip install pyocd"),
        "no_tool": "[!] Weder pyOCD noch OpenOCD gefunden.\n    Empfohlen:  pip install pyocd",
        "pack_installing": "[i] Installiere CMSIS-Pack für {t} (einmalig, Internet nötig)...",
        "pack_fail": "[!] Pack-Installation fehlgeschlagen. Manuell:  pyocd pack install {pack}",
        "build_done": "\n[✓] Ohne Flashen erstellt: {out}",
        "plate_untouched": "    Platine unberührt — Datei kann geprüft/verglichen werden.",
        "dump_saved": "\n[✓] Backup gespeichert: {out}",
        "dump_fail": "\n[✗] Dump fehlgeschlagen (Code {rc}).",
        "fw_not_found": "[!] Firmware nicht gefunden: {key}",
        "list_header": "\nVerfügbare Firmware:",
        "sha_mismatch": "[!] Prüfsumme der eingebetteten Firmware {key} stimmt nicht.",
        "cmd_label": "\n[+] {b}-Befehl:",
        "wiring": ("\nST-Link → Platine (SWD) Verdrahtung:\n"
                   "   SWDIO  (DIO)   →  SWDIO\n"
                   "   SWCLK  (CLK)   →  SWCLK\n"
                   "   GND            →  GND\n"
                   "   3.3V           →  3.3-V-Schiene der Platine (MCU VDD) — versorgt den Chip\n"
                   "   RST            →  nicht anschließen\n"
                   "Versorgung über ST-Link 3.3 V, kein Netz. Display bleibt am Tisch dunkel (normal)."),
        "verify_start": "[i] Prüfe: lese Firmware von der Platine zurück...",
        "verify_ok": "[✓] Verifizierung bestanden: Firmware stimmt Byte für Byte überein.",
        "verify_fail": "[✗] Verifizierung FEHLGESCHLAGEN: Rücklese-Unterschied — neu flashen.",
        "press_enter_exit": "Enter zum Schließen drücken.",
        "offer_install": "pyOCD nicht gefunden. Jetzt installieren (pip install pyocd)? [Y/n]: ",
        "installing_pyocd": "[i] Installiere pyOCD (Internet nötig)...",
        "install_failed": "[!] pyOCD-Installation fehlgeschlagen. Manuell: pip install pyocd",
    },
    "es": {
        "banner": "Flasheador secador Creality Space Pi X4 Lite",
        "what_to_flash": "¿Qué flashear? (pulsa un número y Enter)",
        "fw_mod90": "90 °C / 194 °F (subir el máximo)",
        "fw_stock": "Volver a fábrica (75 °C / 167 °F)",
        "exit": "salir",
        "choice_prompt": "Elección [1-{n}, Enter=1, 0={exit}]: ",
        "chosen": "Elegido: {name}",
        "press_digit": "  Pulsa un número de la lista.",
        "calib_header": "Calibración de temperatura:",
        "calib_l1": "  Al calentar la pantalla marca de menos — recomendado +{rec:.0f} °C (+{rec_f:.0f} °F): así 90 °C es correcto.",
        "calib_l2": "  Tu propio valor: termómetro en el orificio frontal del tubo PTFE, offset = termómetro − pantalla.",
        "calib_prompt": "Offset, °C [Enter=+{rec:.0f} / 0 = ninguna / p.ej. 9.5 o -3]: ",
        "need_number": "  Introduce un número (p.ej. 10 o 0).",
        "calib_applied": "[i] Calibración: {off:+.1f} °C  (C1 {base:.0f} → {new:.1f})",
        "calib_limit": "[!] Offset {off:+.1f} °C fuera de ±{lim:.0f}. Revisa las medidas.",
        "calib_already": "[!] C1={cur:.3f} en el firmware, no {base:.0f} — el offset se cuenta desde {base:.0f}.",
        "backend_line": "[i] Backend: {b}",
        "fw_line": "[i] Firmware: {name}",
        "size_line": "    tamaño  : {size} bytes",
        "sha_line": "    sha256  : {sha}",
        "size_warn": "[!] Se esperaban {exp} bytes, se obtuvieron {size}.",
        "safety": ("\n⚠  SEGURIDAD  ⚠\n"
                   "  Conectar el depurador con 220 V aplicados NO se recomienda\n"
                   "  (sin aislamiento confirmado — ver README).\n"
                   "  Seguro: alimentar la placa con 5 V USB.\n"
                   "  Líneas: SWDIO · SWCLK · GND (+ 3.3V/5V si hace falta)."),
        "safety_prompt": "¿220 V desconectado, depurador conectado? Flashear —  1=sí  0=cancelar: ",
        "yes_skip": "[i] --yes: confirmación omitida.",
        "cancelled": "Cancelado.",
        "success": "\n[✓] Firmware escrito y verificado. Listo.",
        "disconnect_warn": "    Desconecta el depurador antes de aplicar 220 V a la placa.",
        "calib_after": "    Calibración {off:+.1f} °C aplicada. Verifica con termómetro y reflashea con un valor afinado si hace falta.",
        "err_backend": "\n[✗] {b} terminó con código {rc}.",
        "err_hints": "    Causas comunes: sonda no conectada / velocidad incorrecta / falta driver.\n    Prueba --speed 300 (o 200) y alimentación 5 V USB a la placa.",
        "err_win": "    Windows + ST-Link: instala el driver WinUSB con Zadig.",
        "pyocd_missing": ("[!] pyOCD no está instalado. Instálalo con un comando:\n"
                          "      pip install pyocd\n"
                          "    El pack de GD32 se instala solo. (O: OpenOCD + --backend openocd.)"),
        "openocd_missing": ("[!] OpenOCD no encontrado. Instálalo o usa pyOCD:\n"
                            "      pip install pyocd"),
        "no_tool": "[!] No se encontró ni pyOCD ni OpenOCD.\n    Recomendado:  pip install pyocd",
        "pack_installing": "[i] Instalando el pack CMSIS para {t} (una vez, necesita internet)...",
        "pack_fail": "[!] No se pudo instalar el pack. Manual:  pyocd pack install {pack}",
        "build_done": "\n[✓] Creado sin flashear: {out}",
        "plate_untouched": "    La placa no se tocó — puedes revisar/comparar el archivo.",
        "dump_saved": "\n[✓] Copia guardada: {out}",
        "dump_fail": "\n[✗] No se pudo volcar (código {rc}).",
        "fw_not_found": "[!] Firmware no encontrado: {key}",
        "list_header": "\nFirmware disponible:",
        "sha_mismatch": "[!] La suma de control del firmware {key} no coincide.",
        "cmd_label": "\n[+] Comando {b}:",
        "wiring": ("\nConexión ST-Link → placa (SWD):\n"
                   "   SWDIO  (DIO)   →  SWDIO\n"
                   "   SWCLK  (CLK)   →  SWCLK\n"
                   "   GND            →  GND\n"
                   "   3.3V           →  riel de 3.3 V de la placa (VDD del MCU) — alimenta el chip\n"
                   "   RST            →  no conectar\n"
                   "Alimentado por 3.3 V del ST-Link, sin red. La pantalla queda apagada en banco (normal)."),
        "verify_start": "[i] Verificando: leyendo el firmware de la placa...",
        "verify_ok": "[✓] Verificación correcta: el firmware coincide byte a byte.",
        "verify_fail": "[✗] Verificación FALLÓ: no coincide la relectura — vuelve a flashear.",
        "press_enter_exit": "Enter para cerrar.",
        "offer_install": "pyOCD no encontrado. ¿Instalar ahora (pip install pyocd)? [Y/n]: ",
        "installing_pyocd": "[i] Instalando pyOCD (necesita internet)...",
        "install_failed": "[!] No se pudo instalar pyOCD. Manual: pip install pyocd",
    },
    "zh": {
        "banner": "Creality Space Pi X4 Lite 烘干机刷写工具",
        "what_to_flash": "刷什么? (按数字再回车)",
        "fw_mod90": "90 °C / 194 °F (提高上限)",
        "fw_stock": "恢复出厂 (75 °C / 167 °F)",
        "exit": "退出",
        "choice_prompt": "选择 [1-{n}, 回车=1, 0={exit}]: ",
        "chosen": "已选择: {name}",
        "press_digit": "  请按列表中的数字。",
        "calib_header": "温度校准:",
        "calib_l1": "  加热时显示偏低 — 推荐 +{rec:.0f} °C (+{rec_f:.0f} °F): 这样 90 °C 显示才准确。",
        "calib_l2": "  自测: 把温度计插入前面 PTFE 管孔, 偏移 = 温度计 − 显示。",
        "calib_prompt": "偏移, °C [回车=+{rec:.0f} / 0 = 不校准 / 例如 9.5 或 -3]: ",
        "need_number": "  请输入数字 (例如 10 或 0)。",
        "calib_applied": "[i] 校准: {off:+.1f} °C  (C1 {base:.0f} → {new:.1f})",
        "calib_limit": "[!] 偏移 {off:+.1f} °C 超出 ±{lim:.0f} 范围。请检查测量。",
        "calib_already": "[!] 固件中 C1={cur:.3f}, 不是 {base:.0f} — 偏移按 {base:.0f} 计算。",
        "backend_line": "[i] 后端: {b}",
        "fw_line": "[i] 固件: {name}",
        "size_line": "    大小    : {size} 字节",
        "sha_line": "    sha256  : {sha}",
        "size_warn": "[!] 期望 {exp} 字节, 实际 {size}。",
        "safety": ("\n⚠  安  全  ⚠\n"
                   "  接入 220V 市电时连接调试器 不建议 (除非已确认隔离, 见 README)。\n"
                   "  安全做法: 主板由 5V USB 供电时刷写。\n"
                   "  接线: SWDIO · SWCLK · GND (+ 需要时 3.3V/5V)。"),
        "safety_prompt": "220V 已断开、调试器已连接? 刷写 —  1=是  0=取消: ",
        "yes_skip": "[i] --yes: 已跳过确认。",
        "cancelled": "已取消。",
        "success": "\n[✓] 固件已写入并校验。完成。",
        "disconnect_warn": "    给主板接 220V 之前，请先断开调试器。",
        "calib_after": "    已写入校准 {off:+.1f} °C。用温度计核对，必要时用更精确的值重刷。",
        "err_backend": "\n[✗] {b} 退出，代码 {rc}。",
        "err_hints": "    常见原因: 探头未插 / 速度不对 / 缺少驱动。\n    试试 --speed 300 (或 200), 并用 5V USB 给主板供电。",
        "err_win": "    Windows + ST-Link: 用 Zadig 安装 WinUSB 驱动。",
        "pyocd_missing": ("[!] 未安装 pyOCD。一条命令安装:\n"
                          "      pip install pyocd\n"
                          "    GD32 的包会自动安装。(或: OpenOCD + --backend openocd。)"),
        "openocd_missing": ("[!] 未找到 OpenOCD。请安装它，或改用 pyOCD:\n"
                            "      pip install pyocd"),
        "no_tool": "[!] 未找到 pyOCD 或 OpenOCD。\n    推荐:  pip install pyocd",
        "pack_installing": "[i] 正在安装 {t} 的 CMSIS 包 (仅一次, 需要联网)...",
        "pack_fail": "[!] 安装包失败。手动:  pyocd pack install {pack}",
        "build_done": "\n[✓] 已生成 (未刷写): {out}",
        "plate_untouched": "    主板未改动 — 可检查/比对该文件。",
        "dump_saved": "\n[✓] 备份已保存: {out}",
        "dump_fail": "\n[✗] 读取失败 (代码 {rc})。",
        "fw_not_found": "[!] 未找到固件: {key}",
        "list_header": "\n可用固件:",
        "sha_mismatch": "[!] 内置固件 {key} 校验和不匹配。",
        "cmd_label": "\n[+] {b} 命令:",
        "wiring": ("\nST-Link → 主板 (SWD) 接线:\n"
                   "   SWDIO  (DIO)   →  SWDIO\n"
                   "   SWCLK  (CLK)   →  SWCLK\n"
                   "   GND            →  GND\n"
                   "   3.3V           →  主板 3.3V 电源轨 (MCU VDD) — 给芯片供电\n"
                   "   RST            →  不连接\n"
                   "由 ST-Link 3.3V 供电, 无需市电。台面上显示屏不亮属正常。"),
        "verify_start": "[i] 校验: 正在从主板回读固件...",
        "verify_ok": "[✓] 校验通过: 主板上的固件逐字节一致。",
        "verify_fail": "[✗] 校验失败: 回读不一致 — 请重新刷写。",
        "press_enter_exit": "按 Enter 关闭窗口。",
        "offer_install": "未找到 pyOCD。现在安装 (pip install pyocd)? [Y/n]: ",
        "installing_pyocd": "[i] 正在安装 pyOCD (需要联网)...",
        "install_failed": "[!] 安装 pyOCD 失败。手动: pip install pyocd",
    },
}


def t(msgid, **kw):
    s = LANGS.get(_LANG, LANGS["en"]).get(msgid) or LANGS["en"].get(msgid, msgid)
    try:
        return s.format(**kw)
    except (KeyError, IndexError):
        return s


def _init_color():
    """Decide whether to use ANSI color. On Windows, try to enable VT
    processing so escapes render in cmd.exe instead of showing as garbage;
    if that fails, fall back to no color."""
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if sys.platform.startswith("win"):
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)              # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if not k.GetConsoleMode(h, ctypes.byref(mode)):
                return False
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            if not k.SetConsoleMode(h, mode.value | 0x0004):
                return False
        except Exception:
            return False
    return True


USE_COLOR = _init_color()


def c(text, color):
    if not USE_COLOR:
        return text
    return f"{color}{text}{RST}"


# --- embedded firmware -------------------------------------------------------

def firmware_bytes(arg):
    """Return firmware bytes by key (embedded) or by file path."""
    if arg in FW_META:
        blob = _FW_BLOBS.get(arg)
        if not blob:
            sys.exit(c(t("fw_not_found", key=arg), RED))
        data = gzip.decompress(base64.b64decode(blob))
        if hashlib.sha256(data).hexdigest() != FW_META[arg][0]:
            sys.exit(c(t("sha_mismatch", key=arg), RED))
        return data
    if os.path.isfile(arg):
        return open(arg, "rb").read()
    sys.exit(c(t("fw_not_found", key=arg), RED))


def materialize(arg, offset, out_path=None):
    """Write the firmware (calibrated if offset != 0) to out_path or a temp
    file; return the path."""
    data = bytearray(firmware_bytes(arg))
    if offset:
        if not -CAL_LIMIT <= offset <= CAL_LIMIT:
            sys.exit(c(t("calib_limit", off=offset, lim=CAL_LIMIT), RED))
        cur = struct.unpack("<f", data[CAL_ADDR:CAL_ADDR + 4])[0]
        if abs(cur - CAL_BASE) > 0.01:
            print(c(t("calib_already", cur=cur, base=CAL_BASE), YEL))
        new_c1 = CAL_BASE - offset
        data[CAL_ADDR:CAL_ADDR + 4] = struct.pack("<f", new_c1)
        print(c(t("calib_applied", off=offset, base=CAL_BASE, new=new_c1), GREEN))
    if out_path:
        path = out_path
    else:
        fd, path = tempfile.mkstemp(prefix="dryer_", suffix=".bin")
        os.close(fd)
    with open(path, "wb") as f:
        f.write(data)
    return path


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --- interactive prompts (digits only) ---------------------------------------

def choose_language():
    global _LANG
    print(c("\n  Язык / Language / Sprache / Idioma / 语言", BOLD))
    for i, (_code, name) in enumerate(LANG_ORDER, 1):
        print(f"    {c(str(i), BOLD)}) {name}")
    while True:
        s = input(f"  [1-{len(LANG_ORDER)}, Enter=1]: ").strip()
        if s == "":
            s = "1"
        if s.isdigit() and 1 <= int(s) <= len(LANG_ORDER):
            _LANG = LANG_ORDER[int(s) - 1][0]
            return
        print("  ?")


def choose_firmware():
    """Interactive firmware choice (90 C mod or factory revert). Returns the key."""
    items = [("mod90c", "fw_mod90"), ("stock", "fw_stock")]
    print(c(f"\n  {t('banner')}", BOLD))
    print(c("  " + "─" * 46, BOLD))
    print("\n" + t("what_to_flash") + "\n")
    for i, (_key, lk) in enumerate(items, 1):
        mark = GREEN if i == 1 else RST
        print(f"  {c(str(i), BOLD)}) {c(t(lk), mark)}")
    print(f"  {c('0', BOLD)}) {t('exit')}\n")
    while True:
        s = input(t("choice_prompt", n=len(items), exit=t("exit"))).strip()
        if s == "":
            s = "1"
        if s == "0":
            sys.exit(0)
        if s.isdigit() and 1 <= int(s) <= len(items):
            key, lk = items[int(s) - 1]
            print(c(t("chosen", name=t(lk)), GREEN))
            return key
        print(c(t("press_digit"), YEL))


def ask_calibration():
    print(c("\n" + t("calib_header"), BOLD))
    print(t("calib_l1", rec=CAL_RECOMMENDED, rec_f=CAL_RECOMMENDED * 1.8))
    print(t("calib_l2"))
    while True:
        s = input(t("calib_prompt", rec=CAL_RECOMMENDED)).strip().replace(",", ".")
        if s == "":
            return CAL_RECOMMENDED
        try:
            return float(s)
        except ValueError:
            print(c(t("need_number"), YEL))


def safety_gate(assume_yes):
    print(c(t("safety"), RED))
    if assume_yes:
        print(c(t("yes_skip"), YEL))
        return
    ans = input(t("safety_prompt")).strip().lower()
    if ans not in ("1", "yes", "y", "да", "д", "ja", "j", "si", "sí"):
        print(c(t("cancelled"), YEL))
        sys.exit(0)


# --- flashing backends -------------------------------------------------------

def find_pyocd():
    """Locate a working pyocd; return its launch command (list) or None.
    Order: current interpreter -> console script -> other Python interpreters
    (on macOS pyocd is often installed under a different Python)."""
    if importlib.util.find_spec("pyocd") is not None:
        return [sys.executable, "-m", "pyocd"]
    found = shutil.which("pyocd")
    if found:
        return [found]
    seen = {os.path.realpath(sys.executable)}
    for name in ("python3", "python", "/usr/bin/python3",
                 "/opt/homebrew/bin/python3", "/usr/local/bin/python3"):
        exe = shutil.which(name) if "/" not in name else (name if os.path.isfile(name) else None)
        if not exe:
            continue
        real = os.path.realpath(exe)
        if real in seen:
            continue
        seen.add(real)
        try:
            if subprocess.run([exe, "-c", "import pyocd"],
                              capture_output=True).returncode == 0:
                return [exe, "-m", "pyocd"]
        except Exception:
            pass
    return None


def find_openocd(explicit=None):
    if explicit:
        if os.path.isfile(explicit) and os.access(explicit, os.X_OK):
            return explicit
        sys.exit(c(f"[!] --openocd: {explicit} ?", RED))
    found = shutil.which("openocd")
    if found:
        return found
    candidates = []
    if sys.platform == "darwin":
        candidates += ["/opt/homebrew/bin/openocd", "/usr/local/bin/openocd"]
        home = os.path.expanduser("~")
        for d in ("Downloads", ""):
            base = os.path.join(home, d) if d else home
            if os.path.isdir(base):
                for name in os.listdir(base):
                    if name.startswith("xpack-openocd"):
                        candidates.append(os.path.join(base, name, "bin", "openocd"))
    elif sys.platform.startswith("win"):
        candidates += [r"C:\openocd\bin\openocd.exe", r"C:\Program Files\OpenOCD\bin\openocd.exe",
                       os.path.expandvars(r"%LOCALAPPDATA%\openocd\bin\openocd.exe")]
    else:
        candidates += ["/usr/bin/openocd", "/usr/local/bin/openocd"]
    for cand in candidates:
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def try_install_pyocd():
    """Offer to pip-install pyocd into the running interpreter; return its launch
    command on success or None. Skipped when stdin is not interactive."""
    if not sys.stdin.isatty():
        return None
    ans = input(t("offer_install")).strip().lower()
    if ans not in ("", "y", "yes", "д", "да", "j", "s", "1"):
        return None
    print(c(t("installing_pyocd"), YEL))
    rc = subprocess.run([sys.executable, "-m", "pip", "install", "pyocd"]).returncode
    if rc != 0:
        print(c(t("install_failed"), RED))
        return None
    return [sys.executable, "-m", "pyocd"]


def resolve_backend(args):
    pref = getattr(args, "backend", "auto")
    pyocd = find_pyocd()
    if pref == "pyocd":
        if pyocd:
            return "pyocd", pyocd
        pyocd = try_install_pyocd()
        if pyocd:
            return "pyocd", pyocd
        sys.exit(c(t("pyocd_missing"), RED))
    if pref == "openocd":
        oo = find_openocd(args.openocd)
        if oo:
            return "openocd", oo
        sys.exit(c(t("openocd_missing"), RED))
    if pyocd:
        return "pyocd", pyocd
    oo = find_openocd(args.openocd)
    if oo:
        return "openocd", oo
    # nothing found — offer to install pyocd
    pyocd = try_install_pyocd()
    if pyocd:
        return "pyocd", pyocd
    sys.exit(c(t("no_tool"), RED))


def ensure_pyocd_pack(pyocd):
    try:
        out = subprocess.run(pyocd + ["list", "--targets"], capture_output=True, text=True).stdout
    except Exception:
        out = ""
    if PYOCD_TARGET in out:
        return
    print(c(t("pack_installing", t=PYOCD_TARGET), YEL))
    if subprocess.run(pyocd + ["pack", "install", PYOCD_PACK]).returncode != 0:
        sys.exit(c(t("pack_fail", pack=PYOCD_PACK), RED))


def _echo_cmd(backend, cmd):
    shown = cmd[:]
    if shown[:3] == [sys.executable, "-m", "pyocd"]:
        shown = ["python", "-m", "pyocd"] + shown[3:]
    print(c(t("cmd_label", b=backend), BOLD))
    print("    " + " ".join(f'"{x}"' if " " in x else x for x in shown) + "\n")


def flash_image(backend, handle, args, path):
    if backend == "pyocd":
        cmd = handle + ["flash", "-t", args.target, "-f", f"{args.speed}k",
                        "--base-address", hex(FLASH_BASE), path]
    else:
        fw_unix = path.replace("\\", "/")
        iface = INTERFACE_CFG.get(args.interface, args.interface)
        cmd = [handle]
        if args.openocd_scripts:
            cmd += ["-s", args.openocd_scripts]
        cmd += ["-f", iface, "-f", TARGET_CFG, "-c", f"adapter speed {args.speed}",
                "-c", f"program {{{fw_unix}}} {hex(FLASH_BASE)} verify reset exit"]
    _echo_cmd(backend, cmd)
    return subprocess.run(cmd).returncode


def dump_image(backend, handle, args, out):
    out_unix = out.replace("\\", "/")
    if backend == "pyocd":
        cmd = handle + ["cmd", "-t", args.target, "-f", f"{args.speed}k",
                        "-c", f"savemem {hex(FLASH_BASE)} {FLASH_SIZE} {out_unix}",
                        "-c", "reset"]
    else:
        iface = INTERFACE_CFG.get(args.interface, args.interface)
        cmd = [handle]
        if args.openocd_scripts:
            cmd += ["-s", args.openocd_scripts]
        cmd += ["-f", iface, "-f", TARGET_CFG, "-c", f"adapter speed {args.speed}",
                "-c", "init", "-c", "reset halt",
                "-c", f"dump_image {{{out_unix}}} {hex(FLASH_BASE)} {FLASH_SIZE}",
                "-c", "reset run", "-c", "exit"]
    _echo_cmd(backend, cmd)
    return subprocess.run(cmd).returncode


# --- operations --------------------------------------------------------------

def print_wiring():
    """Print the ST-Link -> board (SWD) wiring."""
    print(c(t("wiring"), BOLD))


def verify_flash(backend, handle, args, intended):
    """Read the firmware back from the board and compare byte-for-byte; 0 = match."""
    print(c(t("verify_start"), YEL))
    fd, vtmp = tempfile.mkstemp(prefix="dryer_vrf_", suffix=".bin")
    os.close(fd)
    try:
        rc = dump_image(backend, handle, args, vtmp)
        if rc != 0 or not os.path.isfile(vtmp):
            print(c(t("verify_fail"), RED))
            return 1
        got = open(vtmp, "rb").read()[:len(intended)]
        if got == intended:
            print(c(t("verify_ok"), GREEN))
            return 0
        print(c(t("verify_fail"), RED))
        return 1
    finally:
        if os.path.isfile(vtmp):
            os.remove(vtmp)


def do_flash(args):
    offset = args.calibrate or 0.0

    if args.build_only:
        out = os.path.abspath(args.build_only)
        materialize(args.firmware, offset, out_path=out)
        print(c(t("build_done", out=out), GREEN))
        print(t("sha_line", sha=sha256_file(out)))
        print(c(t("plate_untouched"), YEL))
        sys.exit(0)

    backend, handle = resolve_backend(args)
    print(c(t("backend_line", b=backend), GREEN))
    if backend == "pyocd":
        ensure_pyocd_pack(handle)

    data = firmware_bytes(args.firmware)
    print(c(t("fw_line", name=args.firmware), GREEN))
    print(t("size_line", size=len(data)))
    if len(data) != FLASH_SIZE:
        print(c(t("size_warn", exp=FLASH_SIZE, size=len(data)), YEL))

    rc, verified = 1, False
    tmp = None
    try:
        print_wiring()
        safety_gate(args.yes)
        tmp = materialize(args.firmware, offset)
        intended = open(tmp, "rb").read()
        rc = flash_image(backend, handle, args, tmp)
        if rc == 0:
            verified = verify_flash(backend, handle, args, intended) == 0
    finally:
        if tmp and os.path.isfile(tmp):
            os.remove(tmp)

    if rc == 0 and verified:
        print(c(t("success"), GREEN))
        print(c(t("disconnect_warn"), YEL))
        if offset:
            print(c(t("calib_after", off=offset), YEL))
        sys.exit(0)
    if rc != 0:                       # a verify failure is already explained above
        print(c(t("err_backend", b=backend, rc=rc), RED))
        print(t("err_hints"))
        if backend == "pyocd" and sys.platform.startswith("win"):
            print(t("err_win"))
    sys.exit(rc or 1)


def do_dump(args):
    backend, handle = resolve_backend(args)
    print(c(t("backend_line", b=backend), GREEN))
    if backend == "pyocd":
        ensure_pyocd_pack(handle)
    out = os.path.abspath(args.dump)
    print_wiring()
    safety_gate(args.yes)
    rc = dump_image(backend, handle, args, out)
    if rc == 0 and os.path.isfile(out):
        print(c(t("dump_saved", out=out), GREEN))
        print(t("sha_line", sha=sha256_file(out)))
    else:
        print(c(t("dump_fail", rc=rc), RED))
    sys.exit(rc)


def list_firmwares():
    print(c(t("list_header"), BOLD))
    for key, (sha, lk) in FW_META.items():
        ok = c("✓", GREEN) if _FW_BLOBS.get(key) else c("✗", RED)
        print(f"  {ok} {c(key.ljust(12), BOLD)} {t(lk)}")
    print()


def main():
    p = argparse.ArgumentParser(
        description="Creality Space Pi X4 Lite dryer flasher (GD32F303).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--firmware", "-f", help="mod90c | stock | путь к .bin")
    p.add_argument("--lang", choices=[code for code, _ in LANG_ORDER], help="ru | en | de | es")
    p.add_argument("--backend", "-b", choices=["auto", "pyocd", "openocd"], default="auto",
                   help="pyocd (рекоменд.) | openocd | auto")
    p.add_argument("--speed", "-s", type=int, default=500, help="SWD кГц (по умолч. 500)")
    p.add_argument("--target", default=PYOCD_TARGET, help=f"таргет pyocd (по умолч. {PYOCD_TARGET})")
    p.add_argument("--calibrate", "-c", type=float, metavar="OFFSET",
                   help="калибровка °C: OFFSET к показаниям (рекоменд. +11; можно минус, ±30). 0 — без.")
    p.add_argument("--interface", "-i", default="stlink", help="[openocd] stlink|cmsis-dap|jlink|.cfg")
    p.add_argument("--openocd", help="[openocd] путь к openocd")
    p.add_argument("--openocd-scripts", help="[openocd] путь к scripts")
    p.add_argument("--list", "-l", action="store_true", help="показать прошивки")
    p.add_argument("--dump", metavar="FILE", help="бэкап текущей прошивки в FILE")
    p.add_argument("--build-only", metavar="FILE", help="собрать .bin без прошивки (тест без платы)")
    p.add_argument("--yes", "-y", action="store_true", help="пропустить safety-подтверждение")
    args = p.parse_args()

    global _LANG
    if args.lang:
        _LANG = args.lang

    if args.list:
        list_firmwares()
        return
    if args.dump:
        do_dump(args)
        return

    interactive = not args.firmware
    if interactive:
        if not args.lang:
            choose_language()
        args.firmware = choose_firmware()

    if args.calibrate is None:
        if args.firmware in CALIBRATABLE and interactive:
            args.calibrate = ask_calibration()
        else:
            args.calibrate = 0.0

    do_flash(args)


def _pause_before_close():
    """Keep the console open when launched by double-click on Windows, so the
    output stays readable. A double-click runs with no CLI args; explicit CLI
    runs (with flags) are not paused. No-op on other OSes."""
    try:
        if sys.platform.startswith("win") and len(sys.argv) == 1 and sys.stdin.isatty():
            input("\n" + t("press_enter_exit"))
    except Exception:
        pass


if __name__ == "__main__":
    atexit.register(_pause_before_close)
    try:
        main()
    except KeyboardInterrupt:
        print(c("\n" + t("cancelled"), YEL))
        sys.exit(130)
