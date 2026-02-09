<|ref|>text<|/ref|><|det|>[[272, 118, 769, 133]]<|/det|>
electron affinities and ionization potentials for a wide range of metals,

<|ref|>equation<|/ref|><|det|>[[525, 142, 928, 179]]<|/det|>
 \[ U_{i}^{\mathrm{s e l f}}(q_{i})=\sum_{n=1}^{6}a_{n}q_{i}^{n}. \quad (8) \] 

<|ref|>text<|/ref|><|det|>[[272, 188, 929, 216]]<|/det|>
The contribution to the local density at site i depends on the instantaneous partial charges on all other atoms,

<|ref|>equation<|/ref|><|det|>[[500, 214, 928, 250]]<|/det|>
 \[ \bar{\rho}_{i}=\sum_{j\neq i}\left(1-\frac{q_{j}}{N_{j}}\right)f_{j}(r_{i j}) \quad (9) \] 

<|ref|>text<|/ref|><|det|>[[272, 254, 929, 283]]<|/det|>
with  \( N_{j} \)  as the valency count for atom j. Modifications to the pair potential used in DR-EAM are also supported.

<|ref|>text<|/ref|><|det|>[[271, 289, 931, 391]]<|/det|>
DR-EAM was shown to perform well for bulk metals, metal surfaces, and alloys; and most importantly, it retains the strengths of the unmodified EAM in modeling bulk elastic constants and surface energies (Bhattarai et al., 2019). DR-EAM has similar performance to the unmodified EAM in that both approaches require a double-pass through the force loop, once to compute local densities and again to compute forces and energies. We note that the infrastructure required to implement DR-EAM is a superset of what is required for common fluc-q potentials like the TIP4P-FQ model for water (Rick et al., 1994).

<|ref|>sub_title<|/ref|><|det|>[[273, 412, 474, 430]]<|/det|>
## Acknowledgements

<|ref|>text<|/ref|><|det|>[[271, 441, 931, 543]]<|/det|>
We would like to acknowledge the contributions of Matthew A. Meineke and Teng Lin to the original 00PSE code. Contributions to the OpenMD codebase have also come from: Patrick B. Louden, Joseph R. Michalka, James M. Marr, Anderson D.S. Duraes, Suzanne M. Neidhart, Shenyu Kuang, Madan Lamichhane, Xiuquan Sun, Sydney A. Shavalier, Benjamin M. Harless, Veronica Freund, Minh Nhat Pham, Chunlei Li, Kyle Daily, Alexander Mazanek, and Yang Zheng. Development of OpenMD was carried out with support from the National Science Foundation under grants CHE-0848243, CHE-1362211, CHE-1663773, and CHE-191954648.

<|ref|>sub_title<|/ref|><|det|>[[274, 563, 390, 581]]<|/det|>
## References

<|ref|>text<|/ref|><|det|>[[275, 594, 929, 649]]<|/det|>
Abraham, M. J., Murtola, T., Schulz, R., Páll, S., Smith, J. C., Hess, B., & Lindahl, E. (2015). GROMACS: High performance molecular simulations through multi-level parallelism from laptops to supercomputers. SoftwareX, 1, 19–25. https://doi.org/10.1016/j.softx.2015.06.001

<|ref|>text<|/ref|><|det|>[[275, 658, 929, 686]]<|/det|>
Allen, M. P., & Tildesley, D. J. (2017). Computer simulation of liquids. Oxford University Press. https://doi.org/10.1093/oso/9780198803195.001.0001

<|ref|>text<|/ref|><|det|>[[275, 694, 929, 734]]<|/det|>
Andersen, H. C. (1980). Molecular dynamics simulations at constant pressure and/or temperature. The Journal of Chemical Physics, 72(4), 2384–2393. https://doi.org/10.1063/1.439486

<|ref|>text<|/ref|><|det|>[[275, 743, 929, 784]]<|/det|>
Barber, C. B., Dobkin, D. P., & Huhdanpaa, H. (1996). The quickhull algorithm for convex hulls. ACM Transactions on Mathematical Software, 22(4), 469–483. https://doi.org/10.1145/235815.235821

<|ref|>text<|/ref|><|det|>[[275, 793, 929, 849]]<|/det|>
Barker, M., Chue Hong, N. P., Katz, D. S., Lamprecht, A.-L., Martinez-Ortiz, C., Psomopoulos, F., Harrow, J., Castro, L. J., Gruenpeter, M., Martinez, P. A., & Honeyman, T. (2022). Introducing the FAIR principles for research software. Scientific Data, 9(1), 622. https://doi.org/10.1038/s41597-022-01710-x

<|ref|>text<|/ref|><|det|>[[275, 857, 929, 899]]<|/det|>
Bhattarai, H., Newman, K. E., & Gezelter, J. D. (2019). Polarizable potentials for metals: The density readjusting embedded atom method (DR-EAM). Physical Review B, 99(9), 94106. https://doi.org/10.1103/PhysRevB.99.094106