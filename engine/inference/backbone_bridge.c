/*
 * backbone_bridge.c — C++ Bridge (GGUF Platinum v5.5)
 * Refactorizado por el Tridente (SIGMA/DELTA/OMEGA).
 *
 * Basado en la arquitectura MOSS-TTS para inferencia de baja latencia.
 * Específicamente diseñado para Slingshot v5.4.3 para vectorizar
 * búsquedas de Smart Money Concepts (SMC).
 */

#include "llama.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#ifdef _WIN32
#  define EXPORT __declspec(dllexport)
#else
#  define EXPORT
#endif

typedef struct {
    struct llama_model   *model;
    struct llama_context *ctx;
    int32_t n_embd;
} bridge_handle_t;

/* Inicializar el motor GGUF */
EXPORT bridge_handle_t *bridge_create(
    const char *model_path,
    int32_t     n_ctx,
    int32_t     n_batch,
    int32_t     n_threads,
    int32_t     n_gpu_layers,
    int32_t     type_k,
    int32_t     type_v,
    int32_t     flash_attn)
{
    struct llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = n_gpu_layers;

    struct llama_model *model = llama_model_load_from_file(model_path, mp);
    if (!model) {
        fprintf(stderr, "[GGUF] bridge_create: Error cargando modelo de %s\n", model_path);
        return NULL;
    }

    struct llama_context_params cp = llama_context_default_params();
    cp.n_ctx         = (uint32_t)n_ctx;
    cp.n_batch       = (uint32_t)n_batch;
    cp.n_ubatch      = (uint32_t)n_batch;
    cp.n_threads     = n_threads;
    cp.n_threads_batch = n_threads;
    cp.embeddings    = true;

    if (type_k >= 0) cp.type_k = (enum ggml_type)type_k;
    if (type_v >= 0) cp.type_v = (enum ggml_type)type_v;
    cp.flash_attn_type = (enum llama_flash_attn_type)flash_attn;

    struct llama_context *ctx = llama_init_from_model(model, cp);
    if (!ctx) {
        fprintf(stderr, "[GGUF] bridge_create: Error inicializando contexto\n");
        llama_model_free(model);
        return NULL;
    }

    bridge_handle_t *h = (bridge_handle_t *)malloc(sizeof(bridge_handle_t));
    if (!h) {
        llama_free(ctx);
        llama_model_free(model);
        return NULL;
    }
    h->model  = model;
    h->ctx    = ctx;
    h->n_embd = llama_model_n_embd(model);

    return h;
}

/* Inferencia de un Market Token (Volume-Pattern Scheduling) */
EXPORT int32_t bridge_decode_embd(
    bridge_handle_t *h,
    const float     *embd,
    int32_t          pos,
    int8_t           output)
{
    struct llama_batch batch = llama_batch_init(1, h->n_embd, 1);
    batch.n_tokens = 1;

    // Copiar el embebido del patrón de mercado (Price/Volume/Abs)
    memcpy(batch.embd, embd, (size_t)h->n_embd * sizeof(float));
    batch.pos[0]      = pos;
    batch.n_seq_id[0] = 1;
    batch.seq_id[0][0] = 0;
    batch.logits[0]   = output;

    int32_t ret = llama_decode(h->ctx, batch);
    llama_batch_free(batch);
    return ret;
}

/* Procesamiento por lote (Prefill de 100+ pares en paralelo) */
EXPORT int32_t bridge_decode_embd_batch(
    bridge_handle_t *h,
    const float     *embds,
    int32_t          n_tokens,
    int32_t          pos_start,
    int8_t           output_last)
{
    struct llama_batch batch = llama_batch_init(n_tokens, h->n_embd, 1);
    batch.n_tokens = n_tokens;
    memcpy(batch.embd, embds, (size_t)n_tokens * (size_t)h->n_embd * sizeof(float));

    for (int32_t i = 0; i < n_tokens; i++) {
        batch.pos[i]       = pos_start + i;
        batch.n_seq_id[i]  = 1;
        batch.seq_id[i][0] = 0;
        batch.logits[i]    = (output_last && i == n_tokens - 1) ? 1 : 0;
    }

    int32_t ret = llama_decode(h->ctx, batch);
    llama_batch_free(batch);
    return ret;
}

/* Retornar logits de probabilidad de SMC */
EXPORT float *bridge_get_logits(bridge_handle_t *h, int32_t i)
{
    return llama_get_logits_ith(h->ctx, i);
}

/* Garbage Collection OMEGA */
EXPORT void bridge_free(bridge_handle_t *h)
{
    if (!h) return;
    if (h->ctx)   llama_free(h->ctx);
    if (h->model) llama_model_free(h->model);
    free(h);
}
