from .comfyui_invsr_trimmed import get_configs, InvSamplerSR, BaseSampler, Namespace
import torch
from comfy.utils import ProgressBar
from folder_paths import get_full_path, get_folder_paths, models_dir
import os
import torch.nn.functional as F
import gc
from torch.cuda.amp import autocast
import psutil

def print_memory_stats():
    """Print current memory usage statistics"""
    if torch.cuda.is_available():
        gpu_memory_allocated = torch.cuda.memory_allocated() / (1024**3)
        gpu_memory_cached = torch.cuda.memory_reserved() / (1024**3)
        print(f"GPU Memory allocated: {gpu_memory_allocated:.2f} GB")
        print(f"GPU Memory cached: {gpu_memory_cached:.2f} GB")
    
    process = psutil.Process(os.getpid())
    ram_usage = process.memory_info().rss / (1024**3)
    print(f"RAM Usage: {ram_usage:.2f} GB")

def split_tensor_into_batches(tensor, batch_size):
    """
    Split a tensor into smaller batches of specified size with memory optimization
    
    Args:
        tensor (torch.Tensor): Input tensor of shape (N, C, H, W)
        batch_size (int): Desired batch size for splitting
        
    Returns:
        list: List of tensor indices for batching
    """
    # Get original batch size
    original_batch_size = tensor.size(0)
    
    # Calculate number of full batches and remaining samples
    num_full_batches = original_batch_size // batch_size
    remaining_samples = original_batch_size % batch_size
    
    # Create list of slice indices instead of storing tensors
    batch_indices = []
    
    # Handle full batches
    for i in range(num_full_batches):
        start_idx = i * batch_size
        end_idx = start_idx + batch_size
        batch_indices.append((start_idx, end_idx))
    
    # Handle remaining samples if any
    if remaining_samples > 0:
        batch_indices.append((original_batch_size - remaining_samples, original_batch_size))
    
    return batch_indices

def cleanup_memory():
    """Cleanup GPU and CPU memory"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    gc.collect()

class LoadInvSRModels:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "sd_model": (['stabilityai/sd-turbo'],),
                "invsr_model": (['noise_predictor_sd_turbo_v5.pth'],),
                "dtype": (['fp16', 'fp32', 'bf16'], {"default": "fp16"}),
                "tiled_vae": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("INVSR_PIPE",)
    RETURN_NAMES = ("invsr_pipe",)
    FUNCTION = "loadmodel"
    CATEGORY = "INVSR"

    def loadmodel(self, sd_model, invsr_model, dtype, tiled_vae):
        try:
            match dtype:
                case "fp16":
                    dtype = "torch.float16"
                case "fp32":
                    dtype = "torch.float32"
                case "bf16":
                    dtype = "torch.bfloat16"

            cfg_path = os.path.join(
                os.path.dirname(__file__), "configs", "sample-sd-turbo.yaml"
            )
            sd_path = get_folder_paths("diffusers")[0]

            try:
                ckpt_dir = get_folder_paths("invsr")[0]
            except:
                ckpt_dir = os.path.join(models_dir, "invsr")

            args = Namespace(
                bs=1,
                chopping_bs=8,
                timesteps=None,
                num_steps=1,
                cfg_path=cfg_path,
                sd_path=sd_path,
                started_ckpt_dir=ckpt_dir,
                tiled_vae=tiled_vae,
                color_fix="",
                chopping_size=128,
            )
            configs = get_configs(args)
            configs["sd_pipe"]["params"]["torch_dtype"] = dtype
            
            with torch.no_grad():
                base_sampler = BaseSampler(configs)
            
            return (base_sampler,)
            
        except Exception as e:
            cleanup_memory()
            raise e

class InvSRSampler:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "invsr_pipe": ("INVSR_PIPE",),
                "images": ("IMAGE",),
                "num_steps": ("INT",{"default": 1, "min": 1, "max": 5}),
                "cfg": ("FLOAT",{"default": 1.0, "step":0.1}),
                "batch_size": ("INT",{"default": 1}),
                "chopping_batch_size": ("INT",{"default": 8}),
                "chopping_size": ([128, 256, 512],{"default": 128}),
                "color_fix": (['none', 'wavelet', 'ycbcr'], {"default": "none"}),
                "seed": ("INT", {"default": 123, "min": 0, "max": 2**32 - 1, "step": 1}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "process"
    CATEGORY = "INVSR"

    def process(self, invsr_pipe, images, num_steps, cfg, batch_size, chopping_batch_size, chopping_size, color_fix, seed):
        try:
            print_memory_stats()
            base_sampler = invsr_pipe
            if color_fix == "none":
                color_fix = ""

            cfg_path = os.path.join(
                os.path.dirname(__file__), "configs", "sample-sd-turbo.yaml"
            )
            sd_path = get_folder_paths("diffusers")[0]

            try:
                ckpt_dir = get_folder_paths("invsr")[0]
            except:
                ckpt_dir = os.path.join(models_dir, "invsr")

            args = Namespace(
                bs=batch_size,
                chopping_bs=chopping_batch_size,
                timesteps=None,
                num_steps=num_steps,
                cfg_path=cfg_path,
                sd_path=sd_path,
                started_ckpt_dir=ckpt_dir,
                tiled_vae=base_sampler.configs.tiled_vae,
                color_fix=color_fix,
                chopping_size=chopping_size,
            )
            configs = get_configs(args, log=True)
            configs["cfg_scale"] = cfg
            
            base_sampler.configs = configs
            base_sampler.setup_seed(seed)
            sampler = InvSamplerSR(base_sampler)

            # Move input to device and process
            with torch.no_grad(), autocast(enabled=True):
                images_bchw = images.permute(0,3,1,2)
                og_h, og_w = images_bchw.shape[2:]

                # Calculate new dimensions divisible by 16
                new_height = ((og_h + 15) // 16) * 16
                new_width = ((og_w + 15) // 16) * 16
                resized = False
                
                if og_h != new_height or og_w != new_width:
                    resized = True
                    print(f"[InvSR] - Image not divisible by 16. Resizing to {new_height} (h) x {new_width} (w)")
                    images_bchw = F.interpolate(images_bchw, size=(new_height, new_width), mode='bicubic', align_corners=False)

                batch_indices = split_tensor_into_batches(images_bchw, batch_size)
                results = []
                pbar = ProgressBar(len(batch_indices))

                for start_idx, end_idx in batch_indices:
                    # Process batch
                    batch = images_bchw[start_idx:end_idx].contiguous()
                    result = sampler.inference(image_bchw=batch)
                    results.append(torch.from_numpy(result))
                    pbar.update(1)
                    
                    cleanup_memory()
                    print_memory_stats()

                # Concatenate results efficiently
                result_t = torch.cat(results, dim=0)
                del results
                cleanup_memory()

                # Resize to original dimensions * 4 if needed
                if resized:
                    result_t = F.interpolate(result_t, size=(og_h * 4, og_w * 4), mode='bicubic', align_corners=False)
                
                final_result = result_t.permute(0,2,3,1)
                del result_t
                cleanup_memory()
                
                print_memory_stats()
                return (final_result,)

        except Exception as e:
            cleanup_memory()
            raise e
