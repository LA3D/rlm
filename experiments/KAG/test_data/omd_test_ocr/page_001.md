<|ref|>title<|/ref|><|det|>[[276, 160, 896, 210]]<|/det|>
# OpenMD: A parallel molecular dynamics engine for complex systems and interfaces

<|ref|>text<|/ref|><|det|>[[275, 225, 930, 260]]<|/det|>
Cody R. Drisko \( ^{1} \) , Hemanta Bhattarai \( ^{2} \) , Christopher J. Fennell \( ^{3} \) , Kelsey M. Stocker \( ^{4} \) , Charles F. Vardeman II \( ^{5} \) , and J. Daniel Gezelter \( ^{11} \) 

<|ref|>text<|/ref|><|det|>[[275, 269, 930, 337]]<|/det|>
1 Department of Chemistry and Biochemistry, University of Notre Dame, Notre Dame, IN, United States  
2 Department of Physics, Goshen College, Goshen, IN, United States  
3 Department of Chemistry, Oklahoma State University, Stillwater, OK, United States  
4 Department of Biochemistry, Chemistry, Environment, and Physics, Suffolk University, Boston, MA, United States  
5 Center for Research Computing, University of Notre Dame, Notre Dame, IN, United States  
6 Corresponding author

<|ref|>text<|/ref|><|det|>[[44, 337, 214, 352]]<|/det|>
DOI: 10.21105/joss.07004

<|ref|>text<|/ref|><|det|>[[44, 358, 105, 371]]<|/det|>
Software

<|ref|>text<|/ref|><|det|>[[66, 376, 150, 389]]<|/det|>
■ Review ☐

<|ref|>text<|/ref|><|det|>[[66, 392, 168, 405]]<|/det|>
Repository ☑

<|ref|>text<|/ref|><|det|>[[66, 407, 152, 420]]<|/det|>
■ Archive ☑

<|ref|>text<|/ref|><|det|>[[44, 450, 219, 464]]<|/det|>
Editor: Sarath Menon ☑

<|ref|>text<|/ref|><|det|>[[44, 467, 115, 480]]<|/det|>
Reviewers:

<|ref|>text<|/ref|><|det|>[[66, 485, 170, 498]]<|/det|>
@samwaseda

<|ref|>text<|/ref|><|det|>[[66, 501, 190, 514]]<|/det|>
@prgupta-cpfam

<|ref|>text<|/ref|><|det|>[[44, 524, 234, 551]]<|/det|>
Submitted: 28 June 2024
Published: 01 November 2024

<|ref|>sub_title<|/ref|><|det|>[[44, 558, 97, 570]]<|/det|>
## License

<|ref|>text<|/ref|><|det|>[[43, 571, 262, 624]]<|/det|>
Authors of papers retain copyright and release the work under a Creative Commons Attribution 4.0 International License (CC BY 4.0).

<|ref|>sub_title<|/ref|><|det|>[[277, 371, 377, 389]]<|/det|>
## Summary

<|ref|>text<|/ref|><|det|>[[273, 402, 932, 631]]<|/det|>
Molecular dynamics (MD) simulations help bridge the gap between quantum mechanical calculations, which trade computational resources and system size for chemical accuracy, and continuum simulations, which utilize bulk and surface material properties to make predictions. MD provides the ability to study emergent properties and dynamics for relatively large systems ( \( \sim 10^{6} \)  atoms) over a span of nano- to micro-seconds. MD has been used for simulations of complex systems such as liquids, proteins, membranes, nanoparticles, interfaces, and porous materials, and the approximations used in MD simulations allow us to reach experimentally-relevant time and length scales (Allen & Tildesley, 2017). A molecular dynamics engine leverages classical equations of motion to evolve atomic or molecular coordinates according to a well-defined potential energy function, known as a force field, which is a function of those atomic coordinates. There are a number of high quality molecular dynamics engines that specialize in materials (Thompson et al., 2022) or biomolecular (Brooks et al., 2009; Case et al., 2023) simulations or are models of computational efficiency (Abraham et al., 2015; Eastman et al., 2017). In this paper, we provide background on an open source molecular dynamics engine, OpenMD, which specializes in complex systems and interfaces and was just released into version 3.1.

<|ref|>text<|/ref|><|det|>[[273, 636, 932, 766]]<|/det|>
OpenMD is capable of efficiently simulating a variety of complex systems using standard point-particle atoms, as well as atoms with orientational degrees of freedom (e.g. point multipoles and coarse-grained assemblies), and atoms with additional degrees of freedom (e.g. fluctuating charges). It provides a test-bed for new molecular simulation methodology, while being efficient and easy to use. Liquids, proteins, zeolites, lipids, inorganic nanomaterials, transition metals (bulk, flat interfaces, and nanoparticles), alloys, solid-liquid interfaces, and a wide array of other systems have all been simulated using this code. OpenMD works on parallel computers using the Message Passing Interface (MPI), and is packaged with trajectory analysis and utility programs that are easy to use, extend, and modify.

<|ref|>text<|/ref|><|det|>[[273, 771, 932, 901]]<|/det|>
From the beginning, OpenMD has been an open source project and has been maintained in accordance with the FAIR (findable, accessible, interoperable, and reusable) principles for research software (Barker et al., 2022). It uses a meta-data language that is tightly integrated with input (.omd) and trajectory (.dump) files, providing a standardized, human-readable way to completely describe molecular systems and simulation parameters. All data files are stamped with the code revision that generated that data. This allows OpenMD simulations to be easily reproduced, modified, and reused by others. The <MetaData> section of these files also serves as a form of machine-actionable meta-data, clearly specifying the composition of the molecular system in a manner that promotes interoperability with other software tools.