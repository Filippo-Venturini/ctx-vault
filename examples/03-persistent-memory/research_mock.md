# Transformer Architecture Fundamentals

## Self-Attention Mechanism
The core innovation is self-attention, which allows the model to weigh the importance of different words in a sequence. Unlike RNNs that process sequentially, transformers can attend to all positions simultaneously.

The attention mechanism computes Query (Q), Key (K), and Value (V) vectors for each input. Attention score: softmax(QK^T / sqrt(d_k)) * V

Each word can "look at" every other word and decide how much to focus on each one.

## Multi-Head Attention
Multiple attention heads run in parallel, each learning different relationship aspects. One head might focus on syntactic relationships (subject-verb), while another captures semantic similarities.

## Positional Encoding
Since transformers process all tokens in parallel, they use sinusoidal positional encodings to understand word order:
PE(pos, 2i) = sin(pos/10000^(2i/d_model))

## Architecture
- Encoder: 6 layers with multi-head attention + feed-forward networks
- Decoder: 6 layers with masked self-attention
- Residual connections and layer normalization throughout

## Training Efficiency
Highly parallelizable - no sequential dependencies like RNNs. Much faster training on GPUs.

## Key Insight
Self-attention enables capturing long-range dependencies in a single layer, while RNNs need many stacked layers.""",

    "vision_transformers": """# Vision Transformers (ViT)

## Core Concept
Applying transformer architecture to images by treating image patches as tokens, similar to words in NLP.

## Patch Embedding Innovation
Instead of processing pixels, ViT splits images into fixed-size patches (e.g., 16x16). Each patch is flattened and projected to create embeddings.

For 224x224 image with 16x16 patches: 196 patches (14x14 grid). Each becomes a "token".

## Architecture Differences
- Learnable [CLS] token for classification (like BERT)
- 2D positional embeddings instead of 1D
- Encoder-only (no decoder for classification)
- Pre-trained on large datasets (ImageNet-21k, JFT-300M)

## Performance Insights
Small datasets: ViT underperforms CNNs (lacks inductive biases)
Large-scale pre-training: ViT matches or exceeds CNNs with better efficiency

## Connection to Transformers
Self-attention applies directly - each patch attends to all others. Captures long-range dependencies that CNNs struggle with (e.g., relating opposite image corners in single layer).

## Computational Considerations
- Attention cost scales quadratically with patches
- Smaller patches = better performance but higher compute
- Pre-training dataset size crucial

## Attention Patterns
Early layers: texture/edges
Later layers: object parts and whole objects
Similar to CNN hierarchical learning but emerges naturally from attention.

## Applications
Image classification, object detection (DETR), semantic segmentation, medical imaging.""",

    "llm_scaling": """# Large Language Models - Scaling Laws and Emergent Abilities

## Scaling Laws (Kaplan et al.)
Predictable relationship between model size, dataset size, compute, and performance:
- Performance improves as power law with model size
- Larger models more sample-efficient
- Optimal ratio between model/dataset size for given compute

Formula: Loss ∝ N^(-α) where N = parameters, α ≈ 0.076
Doubling size gives ~5% improvement.

## Emergent Abilities
Certain abilities only appear at scale - sudden emergence at threshold size:

Examples:
- Few-shot learning: GPT-3 (175B) learns from prompt examples
- Chain-of-thought reasoning: only >10B parameters
- Multi-digit multiplication: only at large scale

Intelligence as phase transition - not gradual but sudden emergence.

## Architecture at Scale

Attention bottleneck: O(n²) complexity
Solutions: sparse attention, local windows, memory-efficient implementations

Training stability:
- Gradient clipping, learning rate warmup
- Layer norm placement (pre-norm vs post-norm)
- Mixed precision (fp16/bf16) for memory

Parallelism strategies:
- Data parallelism: batch split across GPUs
- Model parallelism: layers split
- Pipeline parallelism: different layers on different GPUs
- Tensor parallelism: individual layers split

GPT-3 used all four on thousands of GPUs.

## Efficiency vs Performance
Distilled models (DistilBERT, TinyLlama) capture 95%+ performance at 10% size. Most knowledge compressible, but last few percent requires scale.

## Practical Implications
- Medium models (1-10B) sufficient for most applications
- Pre-training expensive, fine-tuning cheap
- RAG can substitute some scaling benefits

## Universal Pattern
Transformer architecture (self-attention) is incredibly general - works for text, vision, massive scale. Same mechanism underlies all applications.

Transformers = universal sequence processors for words, image patches, proteins, etc.