import soundcard as sc

with open('output_utf8.txt', 'w', encoding='utf-8') as f:
    try:
        f.write("=== Speakers ===\n")
        for s in sc.all_speakers():
            f.write(s.name + "\n")

        f.write("\n=== Microphones (no loopback) ===\n")
        mics_no_loopback = sc.all_microphones(include_loopback=False)
        for m in mics_no_loopback:
            f.write(m.name + "\n")

        f.write("\n=== Microphones (with loopback) ===\n")
        mics_all = sc.all_microphones(include_loopback=True)
        for m in mics_all:
            f.write(m.name + "\n")

        no_loopback_names = {m.name for m in mics_no_loopback}
        loopback_mics = [m for m in mics_all if m.name not in no_loopback_names]

        f.write("\n=== Detected Loopback Mics ===\n")
        f.write(str([m.name for m in loopback_mics]) + "\n")

        device = loopback_mics[0] if loopback_mics else sc.default_microphone()
        f.write("\nSelected Device for web.py: " + device.name + "\n")
    except Exception as e:
        f.write("Error: " + str(e) + "\n")
