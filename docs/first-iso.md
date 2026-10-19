# Your first surfd ISO (from Windows or macOS)

You don't need a Fedora machine: GitHub builds the ISO on its own Linux
servers, for free, using `.github/workflows/iso.yml`.

## 1. Build the ISO on GitHub

**Quick test build (no release):**

1. Open the repository on GitHub → **Actions** tab.
2. If GitHub asks, click **I understand my workflows, go ahead and enable them**.
3. In the left list pick **iso** → **Run workflow** → keep `44` → **Run workflow**.
4. Wait (roughly 40–90 minutes; x86_64 and aarch64 build side by side).
5. Open the finished run → **Artifacts** → download **surfd-iso-x86_64**
   (a .zip containing the `.iso` and its `.sha256`).

**A real release** (the ISO appears on the repository's *Releases* page with
`SHA256SUMS`): create a tag, either with Git

```sh
git tag v0.1.0
git push origin v0.1.0
```

or on GitHub: **Releases → Draft a new release → Choose a tag → type `v0.1.0`
→ Create new tag → Publish release**. Publishing creates the tag, which
starts the build; the ISOs are attached to a release automatically.

If a build fails, open the failed step: the most likely first-time problem
is a package name that differs in Fedora 44. The `check` step prints exactly
which ones; fix them in `kickstarts/` and push again.

## 2. Check the download

PowerShell, in your Downloads folder:

```powershell
Get-FileHash .\surfd-0.1.0-f44-x86_64.iso -Algorithm SHA256
Get-Content .\surfd-0.1.0-f44-x86_64.iso.sha256
```

The two hashes must match.

## 3. Try it in a virtual machine

Any of these work on Windows; give the VM **4 GB RAM, 2+ CPUs and a 30 GB disk**.

**VirtualBox (free)**
1. *New* → name `surfd`, ISO image = the downloaded ISO, Type *Linux*, Version *Fedora (64-bit)*;
   tick *Skip Unattended Installation*.
2. Hardware: 4096 MB, 2 CPUs, **Enable EFI**. Disk: 30 GB.
3. Settings → Display → Graphics Controller **VMSVGA**, Video memory 128 MB,
   *Enable 3D Acceleration* on (if the desktop shows glitches, turn it off).
4. Start. The live desktop logs in by itself.

**Hyper-V (Windows Pro/Enterprise)**
1. Quick Create is not suitable; use *New → Virtual Machine*: **Generation 2**, 4096 MB, Default Switch network, 30 GB disk, install from the ISO.
2. VM Settings → Security → Secure Boot template **Microsoft UEFI Certificate Authority** (Fedora's signed shim boots with it).
3. Start, then connect.

**VMware Workstation Player (free for personal use)**
1. *Create a New Virtual Machine* → the ISO → *Linux / Fedora 64-bit* → 30 GB.
2. *Customize Hardware*: 4 GB, 2 CPUs, Display → *Accelerate 3D graphics*.
3. VM Settings → Options → Advanced → Firmware type **UEFI**.

Then follow the VM checklist in [testing.md](testing.md): try the desktop,
run **Install surfd**, restart, remove the ISO from the VM's virtual drive,
and log in to the installed system.

## 4. Real hardware

Write the ISO to a USB stick (8 GB+; it will be erased):

- **Fedora Media Writer** (Windows/macOS): *Select .iso file* → pick the ISO → your USB stick → *Write*.
- **Rufus** (Windows): select the ISO; if asked, choose **Write in DD Image mode**.

Boot from the stick (usually F12, F11, Esc or F8 at power-on). Try the live
desktop first; run `surfd-hwprobe` in a terminal (**Super + Enter**) to see
whether anything needs an extra driver. Use the
[real-hardware checklist](testing.md#real-hardware-checklist) and keep a
backup of anything on the disk you install to.
