from scipy.optimize import direct
import struct_analysis
from scipy.optimize import basinhopping, Bounds, OptimizeResult  # import Minimierungsfunktion aus dem SyiPy-Paket
from scipy.optimize import minimize  # import Minimierungsfunktion aus dem SyiPy-Paket
import numpy as np

ULS_INFEASIBLE_BASE_PENALTY = 1e9
ULS_INFEASIBLE_DEFICIT_FACTOR = 1e6
ULS_PENALTY_WEIGHT = 1.0
SLS1_DEFLECTION_PENALTY_WEIGHT = 1e5
SLS2_FREQUENCY_PENALTY_WEIGHT = 25.0
SLS2_ACCELERATION_PENALTY_WEIGHT = 1e2
SLS2_WALKING_DEFLECTION_PENALTY_WEIGHT = 1e5
SLS2_VELOCITY_PENALTY_WEIGHT = 1e3
FIRE_PENALTY_WEIGHT = 1.0
PT_MIN_REINFORCEMENT_PENALTY_WEIGHT = 1e3


def uls_infeasible_penalty(member, deficit=None):
    if deficit is None:
        deficit = max(member.qk - member.qk_zul_gzt, 0)
    return ULS_INFEASIBLE_BASE_PENALTY + ULS_INFEASIBLE_DEFICIT_FACTOR * deficit


def pt_min_reinforcement_penalty(section):
    m_cr = abs(getattr(section, "m_r_min_reinf", getattr(section, "m_r", 0.0)))
    m_rd_pos = abs(getattr(section, "mu_max", 0.0))
    m_rd_neg = abs(getattr(section, "mu_min", 0.0))
    if m_cr <= 0:
        return 0.0
    if m_rd_pos <= 0 or m_rd_neg <= 0:
        return PT_MIN_REINFORCEMENT_PENALTY_WEIGHT * 1e3
    eta = max(m_cr / m_rd_pos, m_cr / m_rd_neg)
    return PT_MIN_REINFORCEMENT_PENALTY_WEIGHT * max(eta - 1.0, 0.0)


class RandomDisplacementBounds(object):
    # random displacement with bounds for basinhopping optimization
    def __init__(self, xmin, xmax, stepsize=0.1):
        self.xmin = xmin
        self.xmax = xmax
        self.stepsize = stepsize

    def __call__(self, x):
        """take a random step but ensure the new position is within the bounds """
        min_step = np.maximum(self.xmin - x, -self.stepsize)
        max_step = np.minimum(self.xmax - x, self.stepsize)

        random_step = np.random.uniform(low=min_step, high=max_step, size=x.shape)
        xnew = x + random_step

        return xnew


def invalid_rectangular_geometry(h, c_nom, di_xu, di_xo, di_bw):
    d = h - c_nom - di_bw - di_xu / 2
    ds = h - c_nom - di_bw - di_xo / 2
    return d <= 0 or ds <= 0


def unique_start_points(points, bounds):
    starts = []
    seen = set()
    lower = np.array([bnd[0] for bnd in bounds], dtype=float)
    upper = np.array([bnd[1] for bnd in bounds], dtype=float)
    for point in points:
        clipped = np.clip(np.asarray(point, dtype=float), lower, upper)
        key = tuple(np.round(clipped, 6))
        if key not in seen:
            seen.add(key)
            starts.append(clipped)
    return starts


def best_basinhopping(func, var0, bounds, max_iter, minimizer_kwargs):
    system = minimizer_kwargs["args"][0][0]
    span = getattr(system, "l_tot", getattr(system, "li_max", 0.0))
    start_points = unique_start_points(
        [
            var0,
            [bounds[0][0], var0[1], var0[2], var0[3]],
            [max(var0[0], 0.035 * span), 0.014, 0.014, var0[3]],
            [max(var0[0], 0.038 * span), 0.014, 0.020, 0.016],
            [max(var0[0], 0.040 * span), 0.014, 0.020, 0.016],
            [max(var0[0], 0.045 * span), 0.020, 0.020, var0[3]],
            [max(var0[0], 0.050 * span), 0.020, 0.028, 0.016],
            [max(var0[0], 0.055 * span), 0.020, 0.028, 0.016],
            [max(var0[0], 0.060 * span), 0.028, 0.028, var0[3]],
        ],
        bounds,
    )
    niter_each = max(1, int(np.ceil(max_iter / max(len(start_points), 1))))
    bounded_step = RandomDisplacementBounds(np.array([bnd[0] for bnd in bounds]), np.array([bnd[1] for bnd in bounds]))
    best = None
    for start in start_points:
        start_fun = func(np.asarray(start, dtype=float), *minimizer_kwargs.get("args", ()))
        start_result = OptimizeResult(x=np.asarray(start, dtype=float), fun=start_fun, success=True)
        if best is None or start_result.fun < best.fun:
            best = start_result
        opt = basinhopping(
            func,
            start,
            niter=niter_each,
            T=1,
            minimizer_kwargs=minimizer_kwargs,
            take_step=bounded_step,
        )
        if best is None or opt.fun < best.fun:
            best = opt
    return best


def rectangular_feasible_start(var0, bounds, make_member):
    lower = np.array([bnd[0] for bnd in bounds], dtype=float)
    upper = np.array([bnd[1] for bnd in bounds], dtype=float)
    base = np.asarray(var0, dtype=float)
    best_feasible = None
    best_fallback = None
    best_fallback_qk_zul = -float("inf")

    span = 0.0
    try:
        span = make_member(base).system.l_tot
    except Exception:
        pass

    h_candidates = [
        base[0],
        lower[0],
        0.035 * span,
        0.038 * span,
        0.040 * span,
        0.045 * span,
        0.050 * span,
        0.055 * span,
        0.060 * span,
        0.075 * span,
        0.090 * span,
        upper[0],
    ]
    diameter_candidates = [
        base[1],
        base[2],
        0.014,
        0.020,
        0.028,
        0.036,
        0.040,
    ]
    shear_diameter_candidates = [
        base[3],
        0.008,
        0.012,
        0.016,
    ]

    points = []
    for h in h_candidates:
        for di_u in diameter_candidates:
            for di_o in diameter_candidates:
                for di_bw in shear_diameter_candidates:
                    points.append([h, di_u, di_o, di_bw])
    for point in unique_start_points(points, bounds):
        try:
            member = make_member(point)
            member.calc_qk_zul_gzt()
        except Exception:
            continue
        qk_zul = getattr(member, "qk_zul_gzt", 0.0)
        if qk_zul > best_fallback_qk_zul:
            best_fallback_qk_zul = qk_zul
            best_fallback = point
        if qk_zul + 1e-6 >= member.qk:
            if best_feasible is None or member.section.co2 < best_feasible[0]:
                best_feasible = (member.section.co2, point)

    if best_feasible is not None:
        return best_feasible[1]
    if best_fallback is not None:
        return np.clip(best_fallback, lower, upper)
    return np.clip(base, lower, upper)


def calc_uls_penalty(member):
    deficit = max(member.qk - member.qk_zul_gzt, 0.0)
    return ULS_PENALTY_WEIGHT * deficit


def calc_sls1_penalty(member, use_cracked_deflection=True):
    use_cracked = use_cracked_deflection and not (
        member.mkd_p < member.section.mr_p and member.mkd_n > member.section.mr_n
    )
    if use_cracked:
        checks = [
            (member.w_install_ger - member.w_install_adm, member.w_install_adm),
            (member.w_use_ger - member.w_use_adm, member.w_use_adm),
            (member.w_app_ger - member.w_app_adm, member.w_app_adm),
        ]
    else:
        checks = [
            (member.w_install - member.w_install_adm, member.w_install_adm),
            (member.w_use - member.w_use_adm, member.w_use_adm),
            (member.w_app - member.w_app_adm, member.w_app_adm),
        ]
    return SLS1_DEFLECTION_PENALTY_WEIGHT * max(max(value, 0.0) for value, _reference in checks)


def calc_sls2_penalty(member):
    pen_f = member.requirements.f1 - member.f1
    pen_a = member.a_ed - member.requirements.a_cd
    pen_w = member.wf_ed - member.requirements.w_f_cdr1 * member.r1
    pen_v = member.ve_ed - member.ve_cd
    if member.f1 < member.requirements.f1:
        return max(
            SLS2_FREQUENCY_PENALTY_WEIGHT * pen_f,
            SLS2_ACCELERATION_PENALTY_WEIGHT * pen_a,
            SLS2_WALKING_DEFLECTION_PENALTY_WEIGHT * pen_w,
            SLS2_VELOCITY_PENALTY_WEIGHT * pen_v,
            0.0,
        )
    return max(
        SLS2_WALKING_DEFLECTION_PENALTY_WEIGHT * pen_w,
        SLS2_VELOCITY_PENALTY_WEIGHT * pen_v,
        0.0,
    )


def calc_fire_penalty(member):
    member.get_fire_resistance()
    deficit = max(member.requirements.t_fire - member.fire_resistance, 0.0)
    return FIRE_PENALTY_WEIGHT * deficit


def criterion_penalty(member, criterion, include_uls_guard=True, use_cracked_deflection=True):
    penalty_uls = calc_uls_penalty(member)
    if criterion == "ULS":
        return penalty_uls
    if include_uls_guard and penalty_uls > 1e-6:
        return uls_infeasible_penalty(member, penalty_uls)

    guard = penalty_uls if include_uls_guard else 0.0
    if criterion == "SLS1":
        return guard + calc_sls1_penalty(member, use_cracked_deflection=use_cracked_deflection)
    if criterion == "SLS2":
        return guard + calc_sls2_penalty(member)
    if criterion == "FIRE":
        return guard + calc_fire_penalty(member)
    if criterion == "ENV":
        return (
            penalty_uls
            + calc_sls1_penalty(member, use_cracked_deflection=use_cracked_deflection)
            + calc_sls2_penalty(member)
            + calc_fire_penalty(member)
        )
    print("criterion " + criterion + " is not defined")
    print("criterion has to be 'ULS', 'SLS1', 'SLS2', 'FIRE' or 'ENV'")
    return 99.0

# OPTIMIZATION OF CROSS-SECTIONS FOR DEFINED MEMBERS
# ----------------------------------------------------------------------------------------------------------------------


#OPTIMIZATION OF RECTANGULAR CONCRETE CROSS-SECTIONS
#.......................................................................................................................
def opt_rc_rec(m, to_opt="GWP", criterion="ULS", max_iter=100, h_min=0.16):
    # definition of initial values for variables, which are going to be optimized
    h0 = m.section.h  # start value for height corresponds to 1/20 of system length
    di_xu0 = m.section.bw[0][0]  # start value for rebar diameter 40 mm
    di_xo0 = m.section.bw[1][0]  # start value for upper rebar diameter
    di_bw0 = m.section.bw_bg[0]
    var0 = [h0, di_xu0, di_xo0, di_bw0]

    # define bounds of variables
    bh = (h_min, 1.2)  # height between h_min and 1.2 m
    bdi_xu = (0.006, 0.04)  # diameter of rebars between 6 mm and 40 mm
    bdi_xo = (0.006, 0.04)  # diameter of rebars between 6 mm and 40 mm
    bdi_bw = (0.0, 0.016)  # stirrup diameter for shear/punching checks
    bounds = [bh, bdi_xu, bdi_xo, bdi_bw]

    # definition of fixed values of cross-section
    b = m.section.b
    s_xu, s_xo = m.section.bw[0][1], m.section.bw[1][1]
    s_yu, s_yo = m.section.bw[2][1], m.section.bw[3][1]
    di_bw, s_bw, n_bw = m.section.bw_bg[0], m.section.bw_bg[1], m.section.bw_bg[2]
    phi, c_nom, xi, jnt_srch = m.section.phi, m.section.c_nom, m.section.xi, m.section.joint_surcharge

    co, st = m.section.concrete_type, m.section.rebar_type
    if n_bw == 0:
        n_bw = 10
    add_arg = [m.system, co, st, b, s_xu, s_xo, s_yu, s_yo, s_bw, n_bw,
               m.floorstruc, m.requirements, to_opt, criterion, m.g2k, m.qk, phi, c_nom, xi, jnt_srch,
               getattr(m, "check_punching", True)]

    def make_seed_member(point):
        h, di_xu, di_xo, di_bw = point
        section = struct_analysis.RectangularConcrete(
            co, st, b, h, di_xu, s_xu, di_xo, s_xo, di_xu, s_yu, di_xo, s_yo,
            di_bw, s_bw, n_bw, phi, c_nom, xi, jnt_srch
        )
        return struct_analysis.Member2D(
            section, m.system, m.floorstruc, m.requirements, m.g2k, m.qk,
            evaluate_service=False, check_punching=getattr(m, "check_punching", True)
        )

    var0 = rectangular_feasible_start(var0, bounds, make_seed_member)

    opt = best_basinhopping(
        rc_rqs,
        var0,
        bounds,
        max_iter,
        {"args": (add_arg,), "bounds": bounds, "method": "Powell"},
    )
    h, di_xu, di_xo, di_bw = opt.x
    optimized_section = struct_analysis.RectangularConcrete(co, st, b, h, di_xu, s_xu, di_xo, s_xo, di_xu, s_yu, di_xo, s_yo, di_bw, s_bw, n_bw,
                                                            phi, c_nom, xi, jnt_srch)
    return optimized_section

# inner function for optimizing reinforced concrete section for criteria ULS or SLS1 in terms of GWP or height
def rc_rqs(var, add_arg):
    # input: variables, which have to be optimized, additional info about cross-section and system, optimizing option
    # output: if criterion == GWP -> co2 of cross-section, punished by delta 10*(qk_zul-qk)
    # output: if criterion == h -> height of cross-section, punished by delta 1*(qk_zul-qk)
    h, di_xu, di_xo, di_bw = var
    system = add_arg[0]
    concrete = add_arg[1]
    reinfsteel = add_arg[2]
    b = add_arg[3]
    s_xu, s_xo = add_arg[4:6]
    s_yu, s_yo, s_bw, n_bw = add_arg[6:10]
    floorstruc = add_arg[10]
    criteria = add_arg[11]
    to_opt = add_arg[12]
    criterion = add_arg[13]
    g2k = add_arg[14]
    qk = add_arg[15]
    phi, c_nom, xi, jnt_srch = add_arg[16:20]
    check_punching = add_arg[20] if len(add_arg) > 20 else True

    if invalid_rectangular_geometry(h, c_nom, di_xu, di_xo, di_bw):
        return 1e12

    # create section
    section = struct_analysis.RectangularConcrete(concrete, reinfsteel, b, h, di_xu, s_xu, di_xo, s_xo,
                                                  di_xu, s_yu, di_xo, s_yo, di_bw, s_bw, n_bw,
                                                  phi, c_nom, xi, jnt_srch)

    # create member
    member = struct_analysis.Member2D(section, system, floorstruc, criteria, g2k, qk,
                                      check_punching=check_punching)
    member.calc_qk_zul_gzt()  # calculate admissible live load

    penalty = criterion_penalty(
        member,
        criterion,
        include_uls_guard=(criterion == "ENV"),
        use_cracked_deflection=True,
    )
    if to_opt == "GWP":
        return member.section.co2 * (1 + penalty)
    elif to_opt == "h":
        return member.section.h * (1 + penalty)
    return 99


# OPTIMIZATION OF RECTANGULAR POST-TENSIONED CONCRETE CROSS-SECTIONS
# .......................................................................................................................
def opt_pc_rec(m, to_opt="GWP", criterion="ULS", max_iter=100, h_min=0.18): #h_min is set to 18 cm, because of minimum height for post-tensioned systems
    h0 = m.section.h
    di_xu0 = m.section.bw[0][0]
    di_xo0 = m.section.bw[1][0]
    di_bw0 = m.section.bw_bg[0]
    var0 = [h0, di_xu0, di_xo0, di_bw0]

    bounds = [(h_min, 1.2), (0.006, 0.04), (0.006, 0.04), (0.0, 0.016)]

    b = m.section.b
    s_xu, s_xo = m.section.bw[0][1], m.section.bw[1][1]
    s_yu, s_yo = m.section.bw[2][1], m.section.bw[3][1]
    di_bw, s_bw, n_bw = m.section.bw_bg[0], m.section.bw_bg[1], m.section.bw_bg[2]
    if n_bw == 0:
        n_bw = 10
    phi, c_nom, xi, jnt_srch = m.section.phi, m.section.c_nom, m.section.xi, m.section.joint_surcharge
    co, st, pt = m.section.concrete_type, m.section.rebar_type, m.section.pt_steel_type

    add_arg = [
        m.system, co, st, pt, b, s_xu, s_xo, s_yu, s_yo, s_bw, n_bw,
        m.floorstruc, m.requirements, to_opt, criterion, m.g2k, m.qk,
        phi, c_nom, xi, jnt_srch, m.section.layout, m.section.c_nom_pt, m.section.A_p,
        getattr(m, "check_punching", True)
    ]

    def make_seed_member(point):
        h, di_xu, di_xo, di_bw = point
        section = struct_analysis.PostTensionedConcrete(
            co, st, pt, m.system.lx, m.system.ly, b, h, di_xu, s_xu, di_xo, s_xo,
            di_xu, s_yu, di_xo, s_yo, di_bw, s_bw, n_bw, phi, c_nom, xi, jnt_srch,
            m.section.layout, m.section.c_nom_pt, m.section.A_p, compute_stiffness=False
        )
        return struct_analysis.Member2D(
            section, m.system, m.floorstruc, m.requirements, m.g2k, m.qk,
            evaluate_service=False, check_punching=getattr(m, "check_punching", True)
        )

    var0 = rectangular_feasible_start(var0, bounds, make_seed_member)

    evaluation_cache = {}

    def cached_pc_rqs(var, args):
        # Powell revisits the same points often; cache only numerically identical
        # designs so the structural model itself remains unchanged.
        key = tuple(np.round(np.asarray(var, dtype=float), 10))
        if key not in evaluation_cache:
            evaluation_cache[key] = pc_rqs(var, args)
        return evaluation_cache[key]

    opt = best_basinhopping(
        cached_pc_rqs,
        var0,
        bounds,
        max_iter,
        {
            "args": (add_arg,),
            "bounds": bounds,
            "method": "Powell",
            "options": {"maxfev": 250, "xtol": 1e-4, "ftol": 1e-4},
        },
    )
    h, di_xu, di_xo, di_bw = opt.x
    return struct_analysis.PostTensionedConcrete(
        co, st, pt, m.system.lx, m.system.ly, b, h, di_xu, s_xu, di_xo, s_xo,
        di_xu, s_yu, di_xo, s_yo, di_bw, s_bw, n_bw, phi, c_nom, xi, jnt_srch,
        m.section.layout, m.section.c_nom_pt, m.section.A_p
    )


def pc_rqs(var, add_arg):
    h, di_xu, di_xo, di_bw = var
    system, concrete, reinfsteel, pt_steel, b = add_arg[0:5]
    s_xu, s_xo, s_yu, s_yo, s_bw, n_bw = add_arg[5:11]
    floorstruc, criteria, to_opt, criterion, g2k, qk = add_arg[11:17]
    phi, c_nom, xi, jnt_srch, layout, c_nom_pt, A_p = add_arg[17:24]
    check_punching = add_arg[24] if len(add_arg) > 24 else True

    if invalid_rectangular_geometry(h, c_nom, di_xu, di_xo, di_bw):
        return 1e12

    evaluate_service = criterion in ("SLS1", "SLS2", "ENV")
    section = struct_analysis.PostTensionedConcrete(
        concrete, reinfsteel, pt_steel, system.lx, system.ly, b, h, di_xu, s_xu, di_xo, s_xo,
        di_xu, s_yu, di_xo, s_yo, di_bw, s_bw, n_bw, phi, c_nom, xi, jnt_srch,
        layout, c_nom_pt, A_p, compute_stiffness=evaluate_service
    )
    # The PT cracking/minimum-reinforcement check is not treated as a hard
    # optimizer wall. A binary rejection made the search escape by increasing
    # the slab height, although a more slender section can reduce Mcr,PT/MRd.
    # Keeping it as a smooth penalty gives the optimizer a useful direction
    # while still making deficient candidates unattractive.
    min_reinf_penalty = pt_min_reinforcement_penalty(section)
    member = struct_analysis.Member2D(
        section, system, floorstruc, criteria, g2k, qk, evaluate_service=evaluate_service,
        check_punching=check_punching
    )
    member.calc_qk_zul_gzt()

    penalty = criterion_penalty(
        member,
        criterion,
        include_uls_guard=(criterion == "ENV"),
        use_cracked_deflection=False,
    )
    penalty += min_reinf_penalty

    if to_opt == "GWP":
        return member.section.co2 * (1 + penalty)
    elif to_opt == "h":
        return member.section.h * (1 + penalty)
    return 99


#OPTIMIZATION OF RIB CONCRETE CROSS-SECTIONS
#.......................................................................................................................
def opt_rc_rib(m, to_opt="GWP", criterion="ULS", max_iter=100):
    # definition of initial values for variables, which are going to be optimized
    h_w0 = m.section.h-m.section.h_f  # start value for height corresponds to 1/20 of system length
    h_f0 = m.section.h_f
    di_x_w0 = m.section.bw_r[0]  # start value for rebar diameter 40 mm
    di_xo0 = m.section.bw[1][0]
    b_w0 = m.section.b_w
    b0 = m.section.b
    var0 = [h_w0, h_f0, di_x_w0, di_xo0, b_w0, b0]

    # define bounds of variables
    bh_f = (0.12, 0.5)  # height between 12 cm and 50 cm
    bh_w = (0.04, 2)  # height between 10 cm and 2.0 m
    bdi_x_w = (0.008, 0.04)  # diameter of rebars between 8 mm and 40 mm
    bdi_xo = (0.008, 0.04)  # upper reinforcement over supports
    bb_w = (0.15, 0.4)  # rib width between 15 and 40 cm
    bb = (0.4, 2.5)  # rib spacing between 0.4 and 2.5 m
    bounds = [bh_w, bh_f, bdi_x_w, bdi_xo, bb_w, bb]

    # definition of fixed values of cross-section
    l0 = m.li_max
    di_xu, s_xu, di_xo, s_xo = m.section.bw[0][0], m.section.bw[0][1], m.section.bw[1][0], m.section.bw[1][1]
    di_pb_bw, s_pb_bw, n_pb_bw = m.section.bw_bg[0], m.section.bw_bg[1], m.section.bw_bg[2]
    n_x_w = m.section.bw_r[1]
    phi, c_nom, xi, jnt_srch = m.section.phi, m.section.c_nom, m.section.xi, m.section.joint_surcharge

    co, st = m.section.concrete_type, m.section.rebar_type
    add_arg = [m.system, co, st, l0, di_xu, s_xu, di_xo, s_xo, n_x_w, di_pb_bw, s_pb_bw, n_pb_bw, m.floorstruc, m.requirements, to_opt, criterion, m.g2k, m.qk]

    # optimize with basinhopping algorithm with bounds also implemented on both levels (inner and outer):
    bounded_step = RandomDisplacementBounds(np.array([b[0] for b in bounds]), np.array([b[1] for b in bounds]))
    opt = basinhopping(rc_rib_rqs, var0, niter=max_iter, T=1, minimizer_kwargs={"args": (add_arg,), "bounds": bounds,
                                                                            "method": "Powell"}, take_step=bounded_step)
    h_w, h_f, di_x_w, di_xo, b_w, b = opt.x
    optimized_section = struct_analysis.RibbedConcrete(co, st, l0, b, b_w, h_f+h_w, h_f, di_xu, s_xu, di_xo, s_xo, di_x_w, n_x_w, di_pb_bw, s_pb_bw, n_pb_bw, phi, c_nom, xi, jnt_srch)
    #print(l0,round(b,5),round(b_w,5), round(h_w,5), round(h_f,5), di_x_w)

    return optimized_section

# inner function for optimizing reinforced concrete section for criteria ULS or SLS1 in terms of GWP or height
def rc_rib_rqs(var, add_arg):
    # input: variables, which have to be optimized, additional info about cross-section and system, optimizing option
    # output: if criterion == GWP -> co2 of cross-section, punished by delta 10*(qk_zul-qk)
    # output: if criterion == h -> height of cross-section, punished by delta 1*(qk_zul-qk)
    h_w, h_f, di_x_w, di_xo, b_w, b = var
    system = add_arg[0]
    concrete = add_arg[1]
    reinfsteel = add_arg[2]
    l0 = add_arg[3]
    #h_f = add_arg[4]
    di_xu, s_xu, _di_xo_initial, s_xo, n_x_w, di_pb_bw, s_pb_bw, n_pb_bw = add_arg[4:12]
    floorstruc = add_arg[12]
    criteria = add_arg[13]
    to_opt = add_arg[14]
    criterion = add_arg[15]
    g2k = add_arg[16]
    qk = add_arg[17]

    # create section
    section = struct_analysis.RibbedConcrete(concrete, reinfsteel, l0, b, b_w, h_f+h_w, h_f, di_xu, s_xu, di_xo, s_xo, di_x_w, n_x_w, di_pb_bw, s_pb_bw, n_pb_bw)

     # create member
    member = struct_analysis.Member1D(section, system, floorstruc, criteria, g2k, qk)
    member.calc_qk_zul_gzt()  # calculate admissible live load
    # define penalty1, if ULS is not fulfilled
    penalty1 = max(member.qk - member.qk_zul_gzt, 0)

    # define penalty2, if SLS1 (deflections) are not fulfilled
    if member.mkd_p < member.section.mr_p and member.mkd_n < member.section.mr_n:
        d1, d2, d3 = [member.w_install - member.w_install_adm, member.w_use - member.w_use_adm,
                      member.w_app - member.w_app_adm]
    else:
        d1, d2, d3 = [member.w_install - member.w_install_adm, member.w_use - member.w_use_adm,
                      member.w_app - member.w_app_adm]
        #d1, d2, d3 = [member.w_install_ger - member.w_install_adm, member.w_use_ger - member.w_use_adm,
        #              member.w_app_ger - member.w_app_adm]
    penalty2 = 1e5 * max(d1, d2, d3, 0)

    # define penalty3, if SLS2 (vibrations) are not fulfilled
    pen_a = member.a_ed - member.requirements.a_cd  # Grössenordnung 1e-2
    pen_w = member.wf_ed - member.requirements.w_f_cdr1 * member.r1  # HBT S. 48. r2 wird gleich 1 gesetzt
    # (Störungen im benachbarten Feld akzeptiert)  # Grössenordnung 1e-5
    pen_v = member.ve_ed - member.ve_cd  # Grössenordnung 1e-3
    if member.f1 < member.requirements.f1:
        pen_f = member.requirements.f1 - member.f1
        penalty3 = max(pen_f * SLS2_FREQUENCY_PENALTY_WEIGHT, pen_a * 1e2, pen_w * 1e5, pen_v * 1e3, 0)
    else:
        penalty3 = max(pen_w * 1e5, pen_v * 1e3, 0)

    # define penalty4, if fire resistance is not fulfilled
    member.get_fire_resistance()
    penalty4 = max(member.requirements.t_fire-member.fire_resistance, 0)

    # optimize ULS only
    if criterion == "ULS":  # optimize ultimate limit state
        if to_opt == "GWP":
            return member.section.co2*(1+penalty1)
        elif to_opt == "h":
            return member.section.h*(1+penalty1)

    # optimize SLS1 (deflections). Make sure, that also ULS is fulfilled
    elif criterion == "SLS1":  # optimize service limit state (deflections)
        if to_opt == "GWP":
            return member.section.co2*(1+penalty2)
        elif to_opt == "h":
            return member.section.h*(1+penalty2)

    # optimize SLS2 (vibrations). Make sure, that also ULS is fulfilled
    elif criterion == "SLS2":
        if to_opt == "GWP":
            to_minimize = member.section.co2*(1+penalty3)
        elif to_opt == "h":
            to_minimize = member.section.h*(1+penalty3)

    # optimize fire resistance only
    elif criterion == "FIRE":
        if to_opt == "GWP":
            return member.section.co2*(1+penalty4)
        elif to_opt == "h":
            return member.section.h * (1+penalty4)

    # optimize solution, which fulfills all requirements (ULS, SLS1 and SLS2, FIRE)
    elif criterion == "ENV":
        if to_opt == "GWP":
            to_minimize = member.section.co2*(1+penalty1+penalty2+penalty3+penalty4)
        elif to_opt == "h":
            to_minimize = member.section.h*(1+penalty1+penalty2+penalty3+penalty4)
    else:
        to_minimize = 99
        print("criterion " + criterion + " is not defined")
        print("criterion has to be 'ULS', 'SLS1', 'SLS2', 'FIRE' or 'ENV'")
    return to_minimize


##----------------------WOOD REQUIREMENTS--------------------------------------------------------------------
# outer function for finding optimal wooden rectangular cross-section
def opt_gzt_wd_rqs(member, criterion="ULS"):
    h_0 = member.section.h
    bnds = [(0.1, 1.2)]
    minimal_h = minimize(wd_rqs_h, h_0, args=[member, criterion], bounds=bnds, method='Powell')
    h_opt = minimal_h.x[0]
    section = struct_analysis.RectangularWood(member.section.wood_type, member.section.b, h_opt)
    return section

# inner function used for optimizing wooden section in terms of height (equals co2)
def wd_rqs_h(h, args):
    m, criterion = args
    querschnitt = struct_analysis.RectangularWood(m.section.wood_type, m.section.b, h, m.section.phi)
    member = struct_analysis.Member1D(querschnitt, m.system, m.floorstruc, m.requirements, m.g2k, m.qk)
    member.calc_qk_zul_gzt()
    penalty1 = max(member.qk - member.qk_zul_gzt, 0)
    if criterion in ("ULS", "ENV") and penalty1 > 1e-6:
        return uls_infeasible_penalty(member, penalty1)
    if criterion == "ULS":
        to_minimize = abs(member.qk - member.qk_zul_gzt)
    elif criterion == "SLS1":
        d1, d2, d3 = [member.w_install - member.w_install_adm, member.w_use - member.w_use_adm,
                      member.w_app - member.w_app_adm]
        # return penalty if w_adm =! w
        penalty2 = 1e5*max(d1, d2, d3, 0)
        to_minimize = member.section.h*(1000+penalty2)
    elif criterion == "SLS2":
        pen_a = member.a_ed - member.requirements.a_cd  # Grössenordnung 1e-2
        pen_w = member.wf_ed - member.requirements.w_f_cdr1*member.r1  # HBT S. 48. r2 wird gleich 1 gesetzt
        # (Störungen im benachbarten Feld akzeptiert)  # Grössenordnung 1e-5
        pen_v = member.ve_ed - member.ve_cd  # Grössenordnung 1e-3
        if member.f1 < member.requirements.f1:
            pen_f = member.requirements.f1 - member.f1
            penalty2 = max(pen_f * SLS2_FREQUENCY_PENALTY_WEIGHT, pen_a*1e2, pen_w*1e5, pen_v*1e3, 0)
        else:
            penalty2 = max(pen_w*1e5, pen_v*1e3, 0)
        to_minimize = member.section.h*(1+penalty2)
    elif criterion == "FIRE":
        # define penalty4, if fire resistance is not fulfilled
        member.get_fire_resistance()
        penalty4 = max(member.requirements.t_fire - member.fire_resistance, 0)
        to_minimize = member.section.h*(1+penalty4)
    elif criterion == "ENV":
        d1, d2, d3 = [member.w_install - member.w_install_adm, member.w_use - member.w_use_adm,
                      member.w_app - member.w_app_adm]
        pen_a = member.a_ed - member.requirements.a_cd  # Grössenordnung 1e-2
        pen_w = member.wf_ed - member.requirements.w_f_cdr1 * member.r1  # HBT S. 48. r2 wird gleich 1 gesetzt
        # (Störungen im benachbarten Feld akzeptiert)  # Grössenordnung 1e-5
        pen_v = member.ve_ed - member.ve_cd  # Grössenordnung 1e-3
        penalty2 = 1e5 * max(d1, d2, d3, 0)
        if member.f1 < member.requirements.f1:
            pen_f = member.requirements.f1 - member.f1
            penalty3 = max(pen_f * SLS2_FREQUENCY_PENALTY_WEIGHT, pen_a * 1e2, pen_w * 1e5, pen_v * 1e3, 0)
        else:
            penalty3 = max(pen_w * 1e5, pen_v * 1e3, 0)
        member.get_fire_resistance()
        penalty4 = max(member.requirements.t_fire - member.fire_resistance, 0)
        to_minimize = member.section.h * (1 + penalty1 + penalty2 + penalty3 + penalty4)
    else:
        to_minimize = 99
        print("criterion " + criterion + " is not defined")
        print("criterion has to be 'ULS', 'SLS1', 'SLS2' or ENV")
    return to_minimize

def opt_wd_rib(m, to_opt="GWP", criterion="ULS", max_iter=100):
    # definition of initial values for variables, which are going to be optimized
    h0 = m.section.h
    b0 = m.section.b
    t20 = m.section.t2
    t30 = m.section.t3
    var0 = [b0, h0, t20, t30]

    # define bounds of variables
    bh = (0.22, 2.0)  # height of rib between 22 cm (minimal requirement b x h = 100 x 220 for R60 according to Lignum 4.1, Table 433-2,
    # Column G) and 200 cm
    bb = (0.1, 0.52)  # width of rib between 10 cm (minimal requirement b x h = 100 x 220 for R60 according to Lignum 4.1, Table 433-2,
    # Column G) and 52 cm
    bt2 = (0.025, 0.16)  # hight of lower sheating between 2.5 cm (minimal requirement for R60 according to Lignum 4.1, Table 433-2,
    # Column G) and 16 cm
    bt3 = (0.027, 0.16)  # hight of lower sheating between 2.7 cm (minimal requirement for R60 according to Lignum 4.1, Table 433-2,
    # Column G) and 16 cm
    bounds = [bb, bh, bt2, bt3]

    # definition of fixed values of cross-section
    l0 = m.li_max
    a = m.section.a
    # t2 = m.section.t2
    # t3 = m.section.t3

    ti1, ti2, ti3 = m.section.wood_type_1, m.section.wood_type_2, m.section.wood_type_3

    add_arg = [m.system, ti1, ti2, ti3, l0, a, m.floorstruc, m.requirements, to_opt, criterion, m.g2k, m.qk]

# optimize with basinhopping algorithm with bounds also implemented on both levels (inner and outer):
    bounded_step = RandomDisplacementBounds(np.array([b[0] for b in bounds]), np.array([b[1] for b in bounds]))
    opt = basinhopping(wd_rib_rqs, var0, niter=max_iter, T=1, minimizer_kwargs={"args": (add_arg,), "bounds": bounds,
                                                                            "method": "Powell"}, take_step=bounded_step)

    b, h, t2, t3 = opt.x
    optimized_section = struct_analysis.RibWood(ti1, ti2, ti3, l0, b, h, a, t2, t3)
    #print(l0, b, h, t2)
    return optimized_section

#inner function for optimizing wood sections for criteria ULS or SLS in terms of GWP or height
def wd_rib_rqs(var, add_arg):
    b, h, t2, t3 = var
    system = add_arg[0]
    timber1 = add_arg[1]
    timber2 = add_arg[2]
    timber3 = add_arg[3]
    l0 = add_arg[4]
    a = add_arg[5]
    #t2 = add_arg[6]
    #t3 = add_arg[6]
    floorstruc = add_arg[6]
    criteria = add_arg[7]
    to_opt = add_arg[8]
    criterion = add_arg[9]
    g2k = add_arg[10]
    qk = add_arg[11]

    # create section
    section = struct_analysis.RibWood(timber1, timber2, timber3, l0, b, h, a, t2, t3)

    # create member
    member = struct_analysis.Member1D(section, system, floorstruc, criteria, g2k, qk)
    member.calc_qk_zul_gzt()  # calculate admissible live load
    # define penalty1, if ULS is not fulfilled
    penalty1 = max(member.qk - member.qk_zul_gzt, 0)
    if criterion in ("ULS", "ENV") and penalty1 > 1e-6:
        return uls_infeasible_penalty(member, penalty1)

    # define penalty2, if SLS1 (deflections) are not fulfilled
    d1, d2, d3 = [member.w_install - member.w_install_adm, member.w_use - member.w_use_adm,
                      member.w_app - member.w_app_adm]
    penalty2 = 1e5 * max(d1, d2, d3, 0)

    # define penalty3, if SLS2 (vibrations) are not fulfilled
    pen_a = member.a_ed - member.requirements.a_cd  # Grössenordnung 1e-2
    pen_w = member.wf_ed - member.requirements.w_f_cdr1 * member.r1  # HBT S. 48. r2 wird gleich 1 gesetzt
    # (Störungen im benachbarten Feld akzeptiert)  # Grössenordnung 1e-5
    pen_v = member.ve_ed - member.ve_cd  # Grössenordnung 1e-3
    if member.f1 < member.requirements.f1:
        pen_f = member.requirements.f1 - member.f1
        penalty3 = max(pen_f * SLS2_FREQUENCY_PENALTY_WEIGHT, pen_a * 1e2, pen_w * 1e5, pen_v * 1e3, 0)
    else:
        penalty3 = max(pen_w * 1e5, pen_v * 1e3, 0)

    # define penalty4, if fire resistance is not fulfilled
    member.get_fire_resistance()
    penalty4 = 0#max(member.requirements.t_fire - member.fire_resistance, 0)

    # optimize ULS only
    if criterion == "ULS":  # optimize ultimate limit state
        if to_opt == "GWP":
            return member.section.co2 * (1 + penalty1)
        elif to_opt == "h":
            return member.section.h * (1 + penalty1)

    # optimize SLS1 (deflections). Make sure, that also ULS is fulfilled
    elif criterion == "SLS1":  # optimize service limit state (deflections)
        if to_opt == "GWP":
            return member.section.co2 * (1 + penalty2)
        elif to_opt == "h":
            return member.section.h * (1 + penalty2)

    # optimize SLS2 (vibrations). Make sure, that also ULS is fulfilled
    elif criterion == "SLS2":
        if to_opt == "GWP":
            to_minimize = member.section.co2 * (1 + penalty3)
        elif to_opt == "h":
            to_minimize = member.section.h * (1 + penalty3)

    # optimize fire resistance only
    elif criterion == "FIRE":
        if to_opt == "GWP":
            return member.section.co2 * (1 + penalty4)
        elif to_opt == "h":
            return member.section.h * (1 + penalty4)

    # optimize solution, which fulfills all requirements (ULS, SLS1 and SLS2, FIRE)
    elif criterion == "ENV":
        if to_opt == "GWP":
            to_minimize = member.section.co2 * (1 + penalty1 + penalty2 + penalty3 + penalty4)
        elif to_opt == "h":
            to_minimize = member.section.h * (1 + penalty1 + penalty2 + penalty3 + penalty4)
    else:
        to_minimize = 99
        print("criterion " + criterion + " is not defined")
        print("criterion has to be 'ULS', 'SLS1', 'SLS2', 'FIRE' or 'ENV'")
    return to_minimize

#-----------------------------------------------------------------------------------------------------------------------
# function for returning optimal section for defined QS-type, system, requirements, loads, criterion and type of optimum
def get_optimized_section(member, criterion, to_opt, max_iter, h_min=0.16):
    if member.section.section_type == "rc_rec":
        # available to_opt arguments: "GWP", "h"
        # available criterion arguments: "ULS", "SLS1", "SLS2"
        return opt_rc_rec(member, to_opt, criterion, max_iter, h_min)
    elif member.section.section_type == "pc_rec":
        # available to_opt arguments: "GWP", "h"
        # available criterion arguments: "ULS", "SLS1", "SLS2"
        return opt_pc_rec(member, to_opt, criterion, max_iter, max(h_min, 0.18))
    elif member.section.section_type == "wd_rec":
        # available criterion arguments: "ULS", "SLS1", "SLS2"
        return opt_gzt_wd_rqs(member, criterion=criterion)
    elif member.section.section_type == "rc_rib":
        # available to_opt arguments: "GWP", "h"
        # available criterion arguments: "ULS", "SLS1", "SLS2"
        return opt_rc_rib(member, to_opt, criterion, max_iter)
    elif member.section.section_type == "wd_rib":
        # available to_opt arguments: "GWP", "h"
        # available criterion arguments: "ULS", "SLS1", "SLS2"
        return opt_wd_rib(member, to_opt, criterion, max_iter)
    else:
        print("There is no optimization for the section type " + member.section.section_type + " available!")
        return member.section
# ----------------------------------------------------------------------------------------------------------------------


# ----------------------------------------------------------------------------------------------------------------------
# OPTIMIZATION OF CROSS-SECTIONS REGARDING PERFORMANCE WITHIN A DEFINED GWP BUDGET
# ----------------------------------------------------------------------------------------------------------------------
def get_opt_sec(section, gwp_budget):
    if section.section_type == "wd_rec":
        # outer function for finding optimal wooden rectangular cross-section
        h_0 = section.h
        bnds = [(0.02, 10.0)]
        minimal_h = minimize(wd_rec_crsc, h_0, args=[section, gwp_budget], bounds=bnds, method='Powell')
        h_opt = minimal_h.x[0]
        opt_section = struct_analysis.RectangularWood(section.wood_type, section.b, h_opt)
        return opt_section

    elif section.section_type == "rc_rec":
        # get initial values
        h_0 = section.h
        di_xu0 = section.bw[0][0]
        var0 = [h_0, di_xu0]

        # define bounds of variables
        bh = (0.06, 2.0)  # height between 6 cm and 2.0 m
        bdi_xu = (0.006, 0.04)  # diameter of rebars between 6 mm and 40 mm
        bounds = [bh, bdi_xu]

        # definition of fixed values of cross-section
        b = section.b
        s_xu, di_xo, s_xo = section.bw[0][1], section.bw[1][0], section.bw[1][1]
        di_bw, s_bw, n_bw = section.bw_bg[0], section.bw_bg[1], section.bw_bg[2]
        phi, c_nom, xi, jnt_srch = section.phi, section.c_nom, section.xi, section.joint_surcharge
        co, st = section.concrete_type, section.rebar_type
        add_arg = [co, st, b, s_xu, di_xo, s_xo, di_bw, s_bw, n_bw, phi, c_nom, xi, jnt_srch, gwp_budget]

        # optimize with basinhopping algorithm with bounds also implemented on both levels (inner and outer):
        bounded_step = RandomDisplacementBounds(np.array([b[0] for b in bounds]), np.array([b[1] for b in bounds]))
        opt = basinhopping(rc_rec_crsc, var0, minimizer_kwargs={"args": (add_arg,), "bounds": bounds,
                                                                "method": "Powell"},
                           take_step=bounded_step)
        h, di_xu = opt.x
        opt_section = struct_analysis.RectangularConcrete(co, st, b, h, di_xu, s_xu, di_xo, s_xo, di_bw, s_bw,
                                                                n_bw, phi, c_nom, xi, jnt_srch)


        return opt_section

    elif section.section_type == "rc_rib":
        # get initial values
        h_0 = section.h
        di_xu0 = section.bw[0][0]
        b_w0 = section.b_w
        b0 = section.b
        var0 = [h_0, di_xu0, b_w0, b0]

        # define bounds of variables
        bh = (0.3, 2)  # height between 6 cm and 1.0 m
        bdi_x_w = (0.01, 0.04)  # diameter of rebars between 6 mm and 40 mm
        bb_w = (0.12, 0.4)  # rib width between 12 and 60 cm
        bb = (1, 1.5)  # rib spacing between 0.5 and 2.5 m
        bounds = [bh, bdi_x_w, bb_w, bb]


        # definition of fixed values of cross-section
        l0 = section.li_max
        h_f = section.h_f
        di_xu, s_xu, di_xo, s_xo = section.bw[0][0], section.bw[0][1], section.bw[1][0], section.bw[1][1]
        di_pb_bw, s_pb_bw, n_pb_bw = section.bw_bg[0], section.bw_bg[1], section.bw_bg[2]
        n_x_w = section.bw_r[1]
        phi, c_nom, xi, jnt_srch = section.phi, section.c_nom, section.xi, section.joint_surcharge
        co, st = section.concrete_type, section.rebar_type
        add_arg = [co, st, l0, h_f, di_xu, s_xu, di_xo, s_xo, n_x_w, di_pb_bw, s_pb_bw, n_pb_bw, phi, c_nom, xi, jnt_srch, gwp_budget]

        # optimize with basinhopping algorithm with bounds also implemented on both levels (inner and outer):
        bounded_step = RandomDisplacementBounds(np.array([b[0] for b in bounds]), np.array([b[1] for b in bounds]))
        opt = basinhopping(rc_rib_crsc, var0, minimizer_kwargs={"args": (add_arg,), "bounds": bounds,
                                                                "method": "Powell"},
                           take_step=bounded_step)
        h, di_x_w, b_w, b = opt.x
        opt_section = struct_analysis.RibbedConcrete(co, st, l0, b, b_w, h, h_f, di_xu, s_xu, di_xo, s_xo, di_x_w, n_x_w, di_pb_bw, s_pb_bw, n_pb_bw, phi, c_nom, xi, jnt_srch)
        return opt_section

    elif section.section_type == "wd_rib":
        # get initial values
        h_0 = section.h
        b_0 = section.b
        var0 = [h_0, b_0]
        print("wd-rib not yet defined for this plot")

## XXXXXXXXXXX neuen Querschnittstyp für optimierung vorbereiten. Für mehrere parameter: basinhopping methode.

    else:
        print("no optimization for section type " + section.section_type + " is defined yet within method get_opt_sec")
        return section

# inner function used for optimizing rectangular wooden section in terms of maximal bending moment and within gwp_budget
def wd_rec_crsc(h, args):
    s, gwp_budget = args
    section_updated = struct_analysis.RectangularWood(s.wood_type, s.b, h)
    penalty = 1e6*max(section_updated.co2-gwp_budget, 0)
    to_minimize = penalty - section_updated.mu_max
    return to_minimize

# inner function for optimizing reinforced concrete section in terms of maximal bending moment and within gwp_budget
def rc_rec_crsc(var, add_arg):
    h, di_xu = var
    concrete = add_arg[0]
    reinfsteel = add_arg[1]
    b = add_arg[2]
    s_xu, di_xo, s_xo = add_arg[3:6]
    di_bw, s_bw, n_bw = add_arg[6:9]
    phi, c_nom, xi, jnt_srch = add_arg[9:13]
    gwp_budget = add_arg[13]
    section_updated = struct_analysis.RectangularConcrete(concrete, reinfsteel, b, h, di_xu, s_xu, di_xo, s_xo, di_bw,
                                                          s_bw, n_bw, phi, c_nom, xi, jnt_srch)
    penalty = 1e6*max(section_updated.co2-gwp_budget, 0)
    to_minimize = penalty - section_updated.mu_max
    return to_minimize

def rc_rib_crsc(var, add_arg):
    h, di_x_w, b_w, b = var
    concrete = add_arg[0]
    reinfsteel = add_arg[1]
    l0 = add_arg[2]
    h_f = add_arg[3]
    di_xu, s_xu, di_xo, s_xo, n_x_w, di_pb_bw, s_pb_bw, n_pb_bw = add_arg[4:11]
    phi, c_nom, xi, jnt_srch = add_arg[12:15]
    gwp_budget = add_arg[16]
    section_updated = struct_analysis.RibbedConcrete(concrete, reinfsteel, l0, b, b_w, h, h_f, di_xu, s_xu, di_xo, s_xo, di_x_w, n_x_w, di_pb_bw, s_pb_bw, n_pb_bw, phi, c_nom, xi, jnt_srch)
    penalty = 1e6*max(section_updated.co2-gwp_budget, 0)
    to_minimize = penalty - section_updated.mu_max
    return to_minimize

## XXXXXXXXXXX neue funktion (returnwert wird minimiert)
