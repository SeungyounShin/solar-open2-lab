"""Run a quick self-contained L2 gravity inversion on starter's Model 3 and
dump arrays for the README GIF. Runs INSIDE the work container (needs SimPEG)."""
import sys
import numpy as np

sys.path.insert(0, "starter")
import starter as s  # noqa: E402  provides mesh, sim_fwd, d_obs, d_clean, sigma_per_pt, rxLoc, m_true

from simpeg import (data, data_misfit, regularization, optimization,       # noqa: E402
                    inverse_problem, inversion, directives)

mesh, sim = s.mesh, s.sim_fwd
dat = data.Data(sim.survey, dobs=s.d_obs, standard_deviation=s.sigma_per_pt)
dmis = data_misfit.L2DataMisfit(data=dat, simulation=sim)
reg = regularization.WeightedLeastSquares(mesh)
opt = optimization.ProjectedGNCG(maxIter=18, lower=-2.0, upper=2.0,
                                 maxIterCG=20, tolCG=1e-3)
invProb = inverse_problem.BaseInvProblem(dmis, reg, opt)
dirs = [
    directives.BetaEstimate_ByEig(beta0_ratio=1e0),
    directives.BetaSchedule(coolingFactor=2.0, coolingRate=1),
    directives.TargetMisfit(),
]
inv = inversion.BaseInversion(invProb, directiveList=dirs)
mrec = inv.run(np.zeros(mesh.nC))

np.savez("/dump/viz.npz",
         m_true=s.m_true, m_rec=mrec, d_obs=s.d_obs, d_clean=s.d_clean,
         rxLoc=s.rxLoc, cc=mesh.cell_centers, shp=np.array(mesh.shape_cells))
print("VIZ_OK m_rec range", float(mrec.min()), float(mrec.max()))
