
In this Fork version, I did some change to optimize the memory handling.

Key optimizations made:

- Memory-efficient batch processing:

Changed split_tensor_into_batches to return indices instead of storing tensor slices
Implemented batch processing using indices to reduce memory overhead

- Added GPU memory management:

Added torch.cuda.empty_cache() after each batch processing
Added gc.collect() to help with Python garbage collection

- Error handling:

Added try-except block to ensure memory cleanup even if an error occurs
Proper cleanup of GPU cache and garbage collection in error cases
Optimized tensor operations:
Reduced unnecessary tensor copies
More efficient handling of batch processing

<div align="center">

# ComfyUI InvSR
[![arXiv](https://img.shields.io/badge/arXiv%20paper-2412.09013-b31b1b.svg)](https://arxiv.org/abs/2412.09013) 

This project is an unofficial ComfyUI implementation of [InvSR](https://github.com/zsyOAOA/InvSR) (Arbitrary-steps Image Super-resolution via Diffusion Inversion)

<img height="500" src="https://github.com/user-attachments/assets/6c057a3c-3355-4060-9161-a88ab6f6d986" />

</div>

## Installation
Navigate to the ComfyUI `/custom_nodes` directory
```bash
git clone https://github.com/yuvraj108c/ComfyUI_InvSR
cd ComfyUI_InvSR

# requires diffusers>=0.28
pip install -r requirements.txt
```

## Usage
- Load [example workflow](workflows/invsr.json) 
- Diffusers model (stabilityai/sd-turbo) will download automatically to `ComfyUI/models/diffusers`
- InvSR model (noise_predictor_sd_turbo_v5.pth) will download automatically to `ComfyUI/models/invsr`
- To deal with large images, e.g, 1k---->4k, set `chopping_size` 256
- If your GPU memory is limited, please set `chopping_batch_size` to 1

## Parameters
- `num_steps`: number of inference steps
- `cfg`: classifier-free guidance scale
- `batch_size`: Controls how many complete images are processed simultaneously
- `chopping_batch_size`: Controls how many patches from the same image are processed simultaneously
- `chopping_size`: Controls the size of patches when splitting large images
- `color_fix`: Method to fix color shift in processed images

## Updates
**03 February 2025**
- Add cfg parameter
- Make image divisible by 16
- Use `mm` to set torch device
  
**31 January 2025**
- Merged https://github.com/yuvraj108c/ComfyUI_InvSR/pull/5 by [wfjsw](https://github.com/wfjsw)
  - Compatibility with `diffusers>=0.28`
  - Massive code refactoring & cleanup

## Citation
```bibtex
@article{yue2024InvSR,
  title={Arbitrary-steps Image Super-resolution via Diffusion Inversion},
  author={Yue, Zongsheng and Kang, Liao and Loy, Chen Change},
  journal = {arXiv preprint arXiv:2412.09013},
  year={2024},
}
```

## License
This project is licensed under [NTU S-Lab License 1.0](LICENSE)

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=yuvraj108c/ComfyUI_InvSR&type=Date)](https://star-history.com/#yuvraj108c/ComfyUI_InvSR&Date)
