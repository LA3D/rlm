<|ref|>text<|/ref|><|det|>[[273, 118, 930, 223]]<|/det|>
cuts off smoothly as  \( r_{ij} \rightarrow R_{c} \) , and the Coulombic kernel is damped using a complementary error function,  \(  f(r) = \frac{\operatorname{erfc}(\alpha r)}{r}  \) . The shifted potential term can be thought of as the interactions of charges with neutralizing charges on the surface of the cutoff sphere. The damping parameter  \(  (\alpha)  \)  can be specified directly in OpenMD, or is set by default from the cutoff radius,  \( \alpha = 0.425 - 0.02R_{c} \) , where the code switches to an undamped kernel for  \( R_{c} > 21.25 \AA \) . The self potential represents the interaction of each charge with its own neutralizing charge on the cutoff sphere, and this term resembles the self-interaction in the Ewald sum,

<|ref|>equation<|/ref|><|det|>[[456, 231, 927, 264]]<|/det|>
 \[ U_{i}^{\mathrm{s e l f}}(q_{i})=-\left(\frac{\mathrm{e r f c}(\alpha R_{c})}{R_{c}}+\frac{\alpha}{\pi^{1/2}}\right)q_{i}^{2}. \quad (5) \] 

<|ref|>text<|/ref|><|det|>[[273, 280, 930, 423]]<|/det|>
DSF offers an attractive compromise between the computational efficiency of Real Space methods  \( \left(\mathcal{O}(N)\right) \)  and the accuracy of the full Ewald sum (Fennell & Gezelter, 2006). The DSF method has also been extended for use with point dipoles and quadrupoles as Gradient Shifted and Taylor Shifted potentials (Lamichhane, Gezelter, et al., 2014) and has been validated for potentials and atomic forces (Lamichhane, Newman, et al., 2014), as well as dielectric properties (Lamichhane et al., 2016), against the full Ewald sum. Note that the Ewald method was extended to point multipoles up to quadrupolar order (Smith, 1982, 1998), and this has also been implemented in OpenMD. The Shifted Force potential generalizes most directly as the Gradient Shifted potential for multipoles, and these are the default electrostatic summation methods in OpenMD.

<|ref|>sub_title<|/ref|><|det|>[[275, 440, 573, 456]]<|/det|>
## Fluctuating Charges and Densities

<|ref|>text<|/ref|><|det|>[[273, 463, 930, 535]]<|/det|>
One way to include the effects of polarizability in molecular simulations is to use electronegativity equalization (Rappé & Goddard, 1991) or fluctuating charges on atomic sites (Rick et al., 1994). OpenMD makes it relatively easy to add extended variables (e.g. charges) on sites to support these methods. In general, the equations of motion are derived from an extended Lagrangian,

<|ref|>equation<|/ref|><|det|>[[375, 543, 927, 583]]<|/det|>
 \[ \mathcal{L}=\sum_{i=1}^{N}\left[\frac{1}{2}m_{i}\dot{r}_{i}^{2}+\frac{1}{2}M_{q}\dot{q}_{i}^{2}\right]-U(\{\mathbf{r}\},\{q\})-\lambda\left(\sum_{i=1}^{N}q_{i}-Q\right) \quad (6) \] 

<|ref|>text<|/ref|><|det|>[[273, 593, 929, 650]]<|/det|>
where the potential depends on both atomic coordinates and the dynamic fluctuating charges on each site. The final term in Eq. 6 constrains the total charge on the system to a fixed value, and  \( M_{q} \)  is a fictitious charge mass that governs the speed of propagation of the extended variables.

<|ref|>text<|/ref|><|det|>[[273, 656, 930, 744]]<|/det|>
A relatively new model for simulating bulk metals, the density readjusting embedded atom method (DR-EAM), has also been implemented (Bhattarai et al., 2019). DR-EAM allows fluctuating densities within the framework of the Embedded Atom Method (EAM) (Daw & Baskes, 1984), by adding an additional degree of freedom, the charge for each atomic site. The total configurational potential energy, U, as a function of both instantaneous positions,  \( \{r\} \) , and partial charges  \( \{q\} \) :

<|ref|>equation<|/ref|><|det|>[[380, 752, 927, 824]]<|/det|>
 \[ \begin{align*}U_{\mathrm{DR-EAM}}(\{\mathbf{r}\},\{q\})&=\sum_{i}F_{i}[\bar{\rho}_{i}]+\frac{1}{2}\sum_{i}\sum_{j\neq i}\phi_{ij}(r_{ij},q_{i},q_{j})\\&\quad+\frac{1}{2}\sum_{i}\sum_{j\neq i}q_{i}q_{j}J(r_{ij})+\sum_{i}U_{i}^{\mathrm{self}}(q_{i})\end{align*} \quad (7) \] 

<|ref|>text<|/ref|><|det|>[[273, 834, 929, 893]]<|/det|>
where the cost of embedding atom i in a total valence density of  \( \bar{\rho}_{i} \)  is computed using the embedding functional,  \( F_{i}[\bar{\rho}_{i}] \) .  \( \phi_{ij} \)  is the pair potential between atoms i and j, and  \( J(r_{ij}) \)  is the Coulomb integral (which can be computed using the DSF approximation above). Lastly,  \( U_{self} \)  is an additional self potential, modeled as a sixth-order polynomial parameterized by