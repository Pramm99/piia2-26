library(Seurat)
library(Matrix)
library(irlba)
library(ggplot2)
library(dplyr)
library(ComplexHeatmap)
library(RColorBrewer)
library(edgeR)
library(DESeq2)
library(tibble)
library(EnhancedVolcano)
library(openxlsx)
library(tidyr)
library(pheatmap)
library(clusterProfiler)
library(org.Hs.eg.db)
library(GSEABase)
library(rstatix)
library(coin)
library(GSVA)
library(ggpubr)
library(msigdbr)

# Open seurat object file previously saved
setwd("C:/Users/34656/OneDrive - Universidade de Santiago de Compostela/Tesis/scRNAseq/HNSC")
seurat_tumor_vs_control <- readRDS("Processed data/GSE181919_seurat_refined.rds")

# Metadata with samples information
samples_info <- data.frame(Samples= sort(unique(seurat_tumor_vs_control$sample.id))) %>% column_to_rownames(var = 'Samples')
samples_info$Age <- c(58,58,53,77,64,56,69,50,57,54,66,73,56,60,53,72,77,56,77,44,58,77,64,56,69,50,73,56,60)
samples_info$Gender <- c("Female","Male","Male","Male","Female","Female","Male","Male","Male","Male","Male","Male","Male","Male","Male","Male","Male","Female","Male","Female","Male","Male","Female","Female","Male","Male","Male","Male","Male")
samples_info$hpv <- c("HPV-","HPV-","HPV-","HPV-","HPV-","HPV-","HPV-","HPV+","HPV-","HPV-","HPV-","HPV-","HPV+","HPV+","HPV-","HPV+","HPV+","HPV-","HPV+","HPV+","HPV-","HPV-","HPV-","HPV-","HPV-","HPV+","HPV-","HPV+","HPV+")

# Pseudobulk aggreagation (counts aggregate to sample level for each celltype)
counts <- AggregateExpression(
  seurat_tumor_vs_control,
  group.by = c("celltype_refined","sample.id"),
  assays = "RNA",
  slot = "counts",
)

counts <- counts$RNA

# Split aggreagation for each celltype
counts.t <- t(counts)
counts.t <- as.data.frame(counts.t)
splitRows <- gsub('_.*','', rownames(counts.t))
counts_split <- split.data.frame(counts.t, f=factor(splitRows))
counts_split_modified <- lapply(counts_split, function(x){
  rownames(x) <- gsub('.*_(.*)','\\1',rownames(x))
  t(x)
})

# Determine total number of cells per sample
total_n_cells <- seurat_tumor_vs_control@meta.data %>% 
  dplyr::count(sample.id) %>%
  rename("n_cells"="n")
total_n_cells$condition = ifelse(grepl('C',total_n_cells$sample.id),'Tumor', 'Control')

# Add number of aggregated cells for each celltype and sample
n_cells <- seurat_tumor_vs_control@meta.data %>% 
  dplyr::count(sample.id, celltype_refined) %>%
  rename("n_cells"="n")
n_cells$condition = ifelse(grepl('C',n_cells$sample.id),'Tumor', 'Control')


## Differential expression analysis in NK cells (Tumor vs Normal)
counts_NK <- counts_split_modified$`NK cells`
# Generate sample level metadata
colData <- data.frame(sample.id=colnames(counts_NK))
colData <- colData %>% mutate(condition = ifelse(grepl('C',sample.id),'Tumor', 'Control')) %>% column_to_rownames(var = 'sample.id')
nk_n_cells <- n_cells[n_cells$celltype_refined == 'NK cells',]
colData$n_cells <- nk_n_cells$n_cells
colData$total_cells <- total_n_cells[total_n_cells$sample.id %in% rownames(colData),]$n_cells
colData <- cbind(colData, samples_info[rownames(colData), , drop = FALSE])
colData <- colData[colData$total_cells > 180,]# remove samples with less than 180 cells
colData$sample.id <- rownames(colData)

# Create DESeq2 object
counts_NK <- counts_NK[,colData$sample.id]
dds <- DESeqDataSetFromMatrix(
  countData = counts_NK,
  colData = colData,
  design = ~ condition
)

# Filtering
keep_genes <- rowSums(counts(dds)>= 10) >= 3 # Remove genes with less than 10 reads in 3 samples
keep_samples <- colData$n_cells >= 10 # Remove samples with less than 10 cells
dds <- dds[keep_genes,keep_samples]

# Run DESeq2
dds <- DESeq(dds)

# Determine differentially expressed genes
res <- results(dds, name = "condition_Tumor_vs_Control")
res <- lfcShrink(dds, coef = "condition_Tumor_vs_Control", res=res)
res <- res[order(res$padj), ]
res_df <- as.data.frame(res)
# Filter significant genes
sig <- res_df %>%
  dplyr::filter(!is.na(padj)) %>%
  dplyr::filter(padj < 0.05)

## Pathway enrichment of DEGs
# Get significant up and downregulated genes
up_sig_genes <- sig %>%
  dplyr::filter(log2FoldChange > 1) %>%
  rownames()
down_sig_genes <- sig %>%
  dplyr::filter(log2FoldChange < -1) %>%
  rownames()

# 1. Upregulated genes enrichment (Biological Process GO)
up_gene_ids <- bitr(
  up_sig_genes,
  fromType = "SYMBOL",
  toType = "ENTREZID",
  OrgDb = org.Hs.eg.db
)

ego <- enrichGO(
  gene = up_gene_ids$ENTREZID,
  OrgDb = org.Hs.eg.db,
  ont = "BP",
  readable = TRUE
)
png("DGE/NK (TvsN)/Enrichment/UP_BP_enrichment.png", width = 3000, height = 3500, res = 300)
dotplot(ego, showCategory = 10)
dev.off()
write.xlsx(ego, "DGE/NK (TvsN)/Enrichment/UP_GO.xlsx", rowNames = FALSE)

# 2. Downregulated genes enrichment (Biological Process GO)
down_gene_ids <- bitr(
  down_sig_genes,
  fromType = "SYMBOL",
  toType = "ENTREZID",
  OrgDb = org.Hs.eg.db
)

ego <- enrichGO(
  gene = down_gene_ids$ENTREZID,
  OrgDb = org.Hs.eg.db,
  ont = "BP",
  readable = TRUE
)
dotplot(ego, showCategory = 10)
write.xlsx(ego, "DGE/NK (TvsN)/Enrichment/DOWN_GO.xlsx", rowNames = FALSE)