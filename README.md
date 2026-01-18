# rembg-clean

**rembg-clean** is a CLI automation tool designed to remove backgrounds from batches of images (PNG, JPG) and optionally process GIMP project files (`.xcf`). 

Beyond standard background removal, it includes a **custom edge-cleaning (defringing) algorithm** specifically tuned to prevent "halos" when placing cut-out subjects onto white backgrounds (common for e-commerce).

## 🛠 Tools & Dependencies

This tool relies on the following libraries and software:
*   **[rembg](https://github.com/danielgatis/rembg)**: Powered by U^2-Net, this performs the AI-based background removal.
*   **Pillow (PIL) & NumPy**: Used for image manipulation and the custom defringing algorithm.
*   **GIMP (Optional)**: Used to convert `.xcf` files to PNG before processing.

## 📦 Installation & Virtual Environment

It is highly recommended to run this tool inside a **Python Virtual Environment (.venv)**. 

### Why use a venv?
A virtual environment creates an isolated container for this project's dependencies. This ensures that the specific versions of libraries (like `numpy` or `onnxruntime`) required by `rembg` do not conflict with other Python projects on your system.

### Setup Guide

1.  **Clone the repository** (or navigate to the folder):
    ```powershell
    cd path\to\rembg-clean
    ```

2.  **Create the virtual environment**:
    ```powershell
    python -m venv .venv
    ```

3.  **Activate the environment**:
    *   **Windows**:
        ```powershell
        \ .\venv\Scripts\activate
        ```
    *   *Linux/macOS*:
        ```bash
        source .venv/bin/activate
        ```

4.  **Install the project**:
    ```powershell
    pip install -e .
    ```

---

## ⚙️ Configuration: GIMP Setup

If you want to process **.xcf** files, you must ensure the tool can find the **GIMP Console** executable.

The tool will look for GIMP in common paths, but for reliability (especially with GIMP 3), you should set the `GIMP_EXECUTABLE` environment variable.

### Setting the Environment Variable
Point this variable to `gimp-console-*.exe` (NOT `gimp.exe` or the UI version).

**Windows Example:**
```powershell
$env:GIMP_EXECUTABLE = "C:\Program Files\GIMP 3\bin\gimp-console-3.0.exe"
```
*(To make this permanent, use `setx` or edit your System Environment Variables).*

> **Note:** GIMP installed via the Microsoft Store is **not supported** for headless automation due to sandbox restrictions. Please use the standard installer from gimp.org.

---

## 🚀 Usage

Once installed and configured, you can run the tool directly from your terminal.

### Basic Syntax
```powershell
rembg-clean "path\to\input_folder" [OPTIONS]
```

### Examples

**1. Basic run (process all images in folder):**
```powershell
rembg-clean "C:\Photos\Products"
```

**2. Specify a separate output folder:**
```powershell
rembg-clean "C:\Photos\Raw" --out "C:\Photos\Cleaned"
```

**3. Adjust cleaning strength (removes more white halo):**
```powershell
rembg-clean "C:\Photos\Products" --strength 0.8
```

### Command Line Arguments

| Argument | Description | Default |
| :--- | :--- | :--- |
| `folder` | **Required.** Input folder containing images to process. | N/A |
| `--out` | Output folder. If omitted, saves files next to originals. | Same as input |
| `--gimp` | Manually specify GIMP path (overrides env var). | None |
| `--model` | Specific `rembg` model to use (e.g., `isnet-general-use`). | `isnet-general-use` |
| `--strength`| Edge cleaning strength (0.0 to 1.0). Lower values preserve more edge detail; higher values remove more halo. | `1.0` |
| `--erode` | Alpha micro-erosion (pixels). Shrinks the mask slightly. | `0` |
| `--skip-existing` | Skips processing if the output file already exists. | `False` |

## ⚠️ Important Notes

*   **First Run Delay**: When running `rembg` for the first time, it may appear frozen for 1-2 minutes. This is normal; it is compiling code via Numba and downloading the AI model.
*   **Performance**: Process runs on CPU by default unless a compatible GPU/ONNX Runtime is configured.
