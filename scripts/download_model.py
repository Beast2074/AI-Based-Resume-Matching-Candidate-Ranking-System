"""
Download BAAI/bge-small-en-v1.5 ONNX model into backend/models.
This ensures the model is bundled with the repository and loaded locally without downloading at runtime.
"""
import os
import sys
from pathlib import Path

def download_model():
    base_dir = Path(__file__).resolve().parent.parent
    target_dir = base_dir / "backend" / "models"
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Target model directory: {target_dir}")
    
    from fastembed import TextEmbedding

    model_name = "BAAI/bge-small-en-v1.5"
    print(f"Initializing FastEmbed for '{model_name}' into '{target_dir}'...")
    
    # Download into target_dir
    model = TextEmbedding(
        model_name=model_name,
        cache_dir=str(target_dir)
    )

    print("Running verification embedding...")
    test_embeddings = list(model.embed(["TalentRank local embedding test."]))
    if not test_embeddings or len(test_embeddings[0]) != 384:
        raise RuntimeError(f"Unexpected embedding output shape: {len(test_embeddings[0]) if test_embeddings else 'None'}")
    
    print(f"SUCCESS: Model downloaded and verified! Embedding dimensions: {len(test_embeddings[0])}")
    print("\nBundled model files:")
    total_size = 0
    for file_path in target_dir.rglob("*"):
        if file_path.is_file():
            size_mb = file_path.stat().st_size / (1024 * 1024)
            total_size += size_mb
            print(f"  {file_path.relative_to(target_dir)}: {size_mb:.2f} MB")
    print(f"\nTotal model size: {total_size:.2f} MB")

if __name__ == "__main__":
    download_model()
