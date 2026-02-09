<|ref|>text<|/ref|><|det|>[[273, 117, 929, 147]]<|/det|>
all test systems (Vardeman et al., 2011), and remains the preferred method of simulating nanoparticles in the isothermal-isobaric (NPT) ensemble with OpenMD.

<|ref|>image<|/ref|><|det|>[[277, 160, 925, 465]]<|/det|>


<|ref|>figure_title<|/ref|><|det|>[[273, 475, 929, 529]]<|/det|>
Figure 1: A Langevin Hull surrounds explicit water solvating a gold nanoparticle. The Langevin Hull imposes an external pressure and temperature bath and maintains isobaric-isothermal conditions without periodic boundaries. (Image created with the help of Dr. Kristina Davis from the Notre Dame Center for Research Computing.)

<|ref|>sub_title<|/ref|><|det|>[[274, 553, 496, 568]]<|/det|>
## Real Space Electrostatics

<|ref|>text<|/ref|><|det|>[[272, 576, 930, 733]]<|/det|>
Electrostatic interactions are one of the most important intramolecular forces and are present in all but the most basic of molecular simulations. These interactions are also long ranged, and are typically the most computationally expensive. As a result, significant effort has gone into balancing the accuracy and efficiency of these calculations. OpenMD implements a number of techniques which are generally classified according to how solvent molecules are incorporated into the systems of interest. Implicit methods, which exclude solvent molecules from the simulation, offer computational efficiency at the cost of accuracy. One example would be the use of a reaction field (Onsager, 1936) for electrostatics coupled with Langevin dynamics to include the hydrodynamic effects of the solvent. Explicit methods which include all solvent molecules directly are the most widely used with OpenMD. Explicit electrostatic methods can further be classified as either Real Space or Ewald-based methods.

<|ref|>text<|/ref|><|det|>[[272, 739, 929, 796]]<|/det|>
The default electrostatics summation method used in OpenMD is a real space, damped-shifted force (DSF) model (Fennell & Gezelter, 2006) which extends and combines the standard shifted potentials of Wolf et al. (1999) and the damped potentials of Zahn et al. (2002). The potential due to the damped-shifted force has the form:

<|ref|>equation<|/ref|><|det|>[[381, 803, 926, 840]]<|/det|>
 \[ U_{\mathrm{Coulomb}}=\frac{1}{4\pi\epsilon_{0}}\left[\sum_{i}\sum_{j>i}U_{\mathrm{DSF}}(q_{i},q_{j},r_{ij})+\sum_{i}U_{\mathrm{self}}^{\mathrm{self}}(q_{i})\right] \quad (3) \] 

<|ref|>text<|/ref|><|det|>[[273, 845, 571, 859]]<|/det|>
where the damped shifted force potential,

<|ref|>equation<|/ref|><|det|>[[330, 866, 926, 903]]<|/det|>
 \[ U_{\mathrm{DSF}}(q_{i},q_{j},r_{ij})=\begin{cases}q_{i}q_{j}\left[f(r_{ij})-f(R_{c})-f^{\prime}(R_{c})(r_{ij}-R_{c})\right],&r_{ij}\leq R_{c}\\0,&r_{ij}>R_{c}\end{cases} \quad (4) \]