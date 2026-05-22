# Final Comparison GWP Analysis

Source workbook: `plots/final_comparison_summary.xlsx`
Rows analysed: `2670`

## Why Spearman Correlation?

The goal of the Spearman analysis is to identify monotonic drivers of GWP inside each slab system.
The optimiser creates nonlinear and sometimes step-like relationships: for example, increasing span may trigger a jump in reinforcement, prestressing force, or slab height.
Spearman correlation ranks the data first and therefore asks whether higher values of a feature generally correspond to higher or lower GWP, without assuming a straight-line relationship.
The analysis is separated by slab system because variables such as tendon force, rib geometry, connector spacing, or timber properties do not exist for every cross-section type.

## Why PCA and K-means?

PCA is used as an exploratory map of the full design space. It compresses many numerical variables into three principal components so that similar variants can be seen together.
The PCA loading tables and plots show which original variables define PC1, PC2 and PC3. K-means is then applied in this reduced space to find groups of variants with similar geometric and material patterns.
This is not used as a design rule; it is a way to detect families, outliers and whether system or material choices dominate the generated dataset.

## Generated Outputs

- `spearman_by_system/spearman_corr_<system>.png`: system-wise correlation heatmaps.
- `feature_rank_spearman_by_system.csv`: ranked monotonic GWP drivers by system.
- `spearman_by_system/feature_rank_<system>_<target>.png`: compact driver rankings.
- `pca_3d/pca_3d_by_system.png`: PCA coloured by slab system.
- `pca_3d/pca_3d_by_material_family.png`: PCA coloured by material family.
- `pca_3d/kmeans_3d_clusters.png`: unsupervised clusters in PCA space.
- `pca_3d/pca_loadings.csv`: variable contributions to PC1, PC2 and PC3.
- `pca_3d/pca_loadings_pc1.png`, `pc2.png`, `pc3.png`: strongest loadings per component.

## Top Spearman Drivers

### Rectangular concrete - gwp_struct
- `geom_h`: rho = 0.964
- `h_total [m]`: rho = 0.960
- `h_struct [m]`: rho = 0.960
- `m_struct [kN/m2]`: rho = 0.960
- `m_total [kN/m2]`: rho = 0.960
- `geom_d`: rho = 0.955
- `geom_ds`: rho = 0.953
- `cost_struct [CHF/m2]`: rho = 0.953

### Rectangular concrete - gwp_total
- `geom_h`: rho = 0.964
- `h_total [m]`: rho = 0.960
- `m_total [kN/m2]`: rho = 0.960
- `h_struct [m]`: rho = 0.960
- `m_struct [kN/m2]`: rho = 0.960
- `geom_d`: rho = 0.955
- `geom_ds`: rho = 0.953
- `cost_total [CHF/m2]`: rho = 0.953

### Rectangular concrete PT band. - gwp_struct
- `span_l_m`: rho = 0.968
- `geom_l_x`: rho = 0.968
- `geom_l_y`: rho = 0.968
- `geom_ds`: rho = 0.963
- `geom_d`: rho = 0.963
- `geom_h`: rho = 0.961
- `geom_dp`: rho = 0.961
- `geom_e_support`: rho = -0.961

### Rectangular concrete PT band. - gwp_total
- `span_l_m`: rho = 0.968
- `geom_l_x`: rho = 0.968
- `geom_l_y`: rho = 0.968
- `geom_ds`: rho = 0.963
- `geom_d`: rho = 0.963
- `geom_h`: rho = 0.961
- `geom_dp`: rho = 0.961
- `geom_e_support`: rho = -0.961

### Rectangular concrete PT dist. - gwp_struct
- `geom_e_support`: rho = -0.970
- `geom_e_midspan`: rho = 0.970
- `geom_h`: rho = 0.970
- `geom_dp`: rho = 0.970
- `geom_d`: rho = 0.968
- `geom_ds`: rho = 0.967
- `cost_struct [CHF/m2]`: rho = 0.966
- `cost_total [CHF/m2]`: rho = 0.966

### Rectangular concrete PT dist. - gwp_total
- `geom_e_support`: rho = -0.970
- `geom_e_midspan`: rho = 0.970
- `geom_h`: rho = 0.970
- `geom_dp`: rho = 0.970
- `geom_d`: rho = 0.968
- `geom_ds`: rho = 0.967
- `cost_total [CHF/m2]`: rho = 0.966
- `cost_struct [CHF/m2]`: rho = 0.966

### Rectangular wood - gwp_struct
- `cost_struct [CHF/m2]`: rho = 0.776
- `cost_total [CHF/m2]`: rho = 0.776
- `m_struct [kN/m2]`: rho = 0.746
- `h_struct [m]`: rho = 0.746
- `geom_h`: rho = 0.746
- `h_total [m]`: rho = 0.745
- `m_total [kN/m2]`: rho = 0.710
- `span_l_m`: rho = 0.597

### Rectangular wood - gwp_total
- `cost_struct [CHF/m2]`: rho = 0.758
- `cost_total [CHF/m2]`: rho = 0.758
- `h_struct [m]`: rho = 0.728
- `m_struct [kN/m2]`: rho = 0.728
- `geom_h`: rho = 0.728
- `h_total [m]`: rho = 0.727
- `m_total [kN/m2]`: rho = 0.697
- `span_l_m`: rho = 0.579

### Ribbed concrete - gwp_struct
- `w_app_mm`: rho = -0.142
- `f1_Hz`: rho = 0.142
- `span_l_m`: rho = 0.000
- `geom_l0`: rho = 0.000

### Ribbed concrete - gwp_total
- `w_app_mm`: rho = -0.142
- `f1_Hz`: rho = 0.142
- `span_l_m`: rho = 0.000
- `geom_l0`: rho = 0.000

### Ribbed timber hollow core - gwp_struct
- `cost_total [CHF/m2]`: rho = 0.514
- `cost_struct [CHF/m2]`: rho = 0.513
- `m_struct [kN/m2]`: rho = 0.488
- `geom_h`: rho = 0.446
- `h_struct [m]`: rho = 0.443
- `h_total [m]`: rho = 0.431
- `geom_t3`: rho = 0.405
- `geom_t2`: rho = 0.368

### Ribbed timber hollow core - gwp_total
- `cost_total [CHF/m2]`: rho = 0.482
- `cost_struct [CHF/m2]`: rho = 0.481
- `m_struct [kN/m2]`: rho = 0.453
- `geom_h`: rho = 0.413
- `h_struct [m]`: rho = 0.410
- `h_total [m]`: rho = 0.399
- `geom_t3`: rho = 0.380
- `span_l_m`: rho = 0.342

### TCC flat, kerve - gwp_struct
- `m_struct [kN/m2]`: rho = 0.639
- `m_total [kN/m2]`: rho = 0.639
- `span_l_m`: rho = 0.636
- `geom_l0`: rho = 0.636
- `geom_h`: rho = 0.634
- `h_struct [m]`: rho = 0.634
- `h_total [m]`: rho = 0.634
- `cost_struct [CHF/m2]`: rho = 0.631

### TCC flat, kerve - gwp_total
- `m_struct [kN/m2]`: rho = 0.639
- `m_total [kN/m2]`: rho = 0.639
- `span_l_m`: rho = 0.636
- `geom_l0`: rho = 0.636
- `geom_h`: rho = 0.634
- `h_struct [m]`: rho = 0.634
- `h_total [m]`: rho = 0.634
- `cost_struct [CHF/m2]`: rho = 0.631

### TCC ribs, DBS - gwp_struct
- `m_struct [kN/m2]`: rho = 0.763
- `m_total [kN/m2]`: rho = 0.763
- `cost_struct [CHF/m2]`: rho = 0.752
- `cost_total [CHF/m2]`: rho = 0.752
- `span_l_m`: rho = 0.750
- `geom_l0`: rho = 0.750
- `f1_Hz`: rho = -0.742
- `w_app_mm`: rho = 0.741

### TCC ribs, DBS - gwp_total
- `m_total [kN/m2]`: rho = 0.762
- `m_struct [kN/m2]`: rho = 0.762
- `cost_total [CHF/m2]`: rho = 0.752
- `cost_struct [CHF/m2]`: rho = 0.752
- `span_l_m`: rho = 0.751
- `geom_l0`: rho = 0.751
- `f1_Hz`: rho = -0.743
- `w_app_mm`: rho = 0.742

## PCA / Cluster Note

PCA points written: `2670`
Use the PCA loading plots before interpreting the axes; PC1, PC2 and PC3 are mathematical directions, not predefined physical quantities.
