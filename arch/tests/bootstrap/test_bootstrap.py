from __future__ import absolute_import, division

from unittest import TestCase
import warnings

import numpy as np
from numpy.random import RandomState
from numpy.testing import assert_allclose, assert_equal
import pandas as pd
from pandas.util.testing import assert_frame_equal, assert_series_equal
import pytest
import scipy.stats as stats

from arch.bootstrap import (CircularBlockBootstrap, IIDBootstrap,
                            IndependentSamplesBootstrap, MovingBlockBootstrap,
                            StationaryBootstrap)
from arch.bootstrap._samplers_python import \
    stationary_bootstrap_sample_python  # noqa
from arch.bootstrap._samplers_python import stationary_bootstrap_sample
from arch.bootstrap.base import _loo_jackknife

try:
    from arch.bootstrap._samplers import stationary_bootstrap_sample as \
        stationary_bootstrap_sample_cython
    HAS_EXTENSION = True
except ImportError:
    HAS_EXTENSION = False


class TestBootstrap(TestCase):

    @staticmethod
    def func(y, axis=0):
        return y.mean(axis=axis)

    @classmethod
    def setup_class(cls):
        warnings.simplefilter("always", RuntimeWarning)

        cls.rng = RandomState(1234)
        cls.y = cls.rng.randn(1000)
        cls.x = cls.rng.randn(1000, 2)
        cls.z = cls.rng.randn(1000, 1)

        cls.y_series = pd.Series(cls.y)
        cls.z_df = pd.DataFrame(cls.z)
        cls.x_df = pd.DataFrame(cls.x)

    def test_numpy(self):
        x, y, z = self.x, self.y, self.z
        bs = IIDBootstrap(y)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(kwdata.keys()), 0)
            assert_equal(y[index], data[0])
        # Ensure no changes to original data
        assert_equal(bs._args[0], y)

        bs = IIDBootstrap(y=y)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(data), 0)
            assert_equal(y[index], kwdata['y'])
            assert_equal(y[index], bs.y)
        # Ensure no changes to original data
        assert_equal(bs._kwargs['y'], y)

        bs = IIDBootstrap(x, y, z)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(data), 3)
            assert_equal(len(kwdata.keys()), 0)
            assert_equal(x[index], data[0])
            assert_equal(y[index], data[1])
            assert_equal(z[index], data[2])

        bs = IIDBootstrap(x, y=y, z=z)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(data), 1)
            assert_equal(len(kwdata.keys()), 2)
            assert_equal(x[index], data[0])
            assert_equal(y[index], kwdata['y'])
            assert_equal(z[index], kwdata['z'])
            assert_equal(y[index], bs.y)
            assert_equal(z[index], bs.z)

    def test_pandas(self):
        x, y, z = self.x_df, self.y_series, self.z_df
        bs = IIDBootstrap(y)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(kwdata.keys()), 0)
            assert_series_equal(y.iloc[index], data[0])
        # Ensure no changes to original data
        assert_series_equal(bs._args[0], y)

        bs = IIDBootstrap(y=y)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(data), 0)
            assert_series_equal(y.iloc[index], kwdata['y'])
            assert_series_equal(y.iloc[index], bs.y)
        # Ensure no changes to original data
        assert_series_equal(bs._kwargs['y'], y)

        bs = IIDBootstrap(x, y, z)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(data), 3)
            assert_equal(len(kwdata.keys()), 0)
            assert_frame_equal(x.iloc[index], data[0])
            assert_series_equal(y.iloc[index], data[1])
            assert_frame_equal(z.iloc[index], data[2])

        bs = IIDBootstrap(x, y=y, z=z)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(data), 1)
            assert_equal(len(kwdata.keys()), 2)
            assert_frame_equal(x.iloc[index], data[0])
            assert_series_equal(y.iloc[index], kwdata['y'])
            assert_frame_equal(z.iloc[index], kwdata['z'])
            assert_series_equal(y.iloc[index], bs.y)
            assert_frame_equal(z.iloc[index], bs.z)

    def test_mixed_types(self):
        x, y, z = self.x_df, self.y_series, self.z
        bs = IIDBootstrap(y, x=x, z=z)
        bs.seed(23456)
        for data, kwdata in bs.bootstrap(10):
            index = bs.index
            assert_equal(len(data), 1)
            assert_equal(len(kwdata.keys()), 2)
            assert_frame_equal(x.iloc[index], kwdata['x'])
            assert_frame_equal(x.iloc[index], bs.x)
            assert_series_equal(y.iloc[index], data[0])
            assert_equal(z[index], kwdata['z'])
            assert_equal(z[index], bs.z)

    def test_state(self):
        bs = IIDBootstrap(np.arange(100))
        bs.seed(23456)
        state = bs.get_state()
        for data, _ in bs.bootstrap(10):
            final = data[0]
        bs.seed(23456)
        for data, _ in bs.bootstrap(10):
            final_seed = data[0]
        bs.set_state(state)
        for data, _ in bs.bootstrap(10):
            final_state = data[0]
        assert_equal(final, final_seed)
        assert_equal(final, final_state)

    def test_reset(self):
        bs = IIDBootstrap(np.arange(100))
        state = bs.get_state()
        for data, _ in bs.bootstrap(10):
            final = data[0]
        bs.reset()
        state_reset = bs.get_state()
        for data, _ in bs.bootstrap(10):
            final_reset = data[0]
        assert_equal(final, final_reset)
        assert_equal(state, state_reset)

    def test_errors(self):
        x = np.arange(10)
        y = np.arange(100)
        with pytest.raises(ValueError):
            IIDBootstrap(x, y)
        with pytest.raises(ValueError):
            IIDBootstrap(index=x)
        bs = IIDBootstrap(y)

        with pytest.raises(ValueError):
            bs.conf_int(self.func, method='unknown')
        with pytest.raises(ValueError):
            bs.conf_int(self.func, tail='dragon')
        with pytest.raises(ValueError):
            bs.conf_int(self.func, size=95)

    def test_cov(self):
        bs = IIDBootstrap(self.x)
        num_bootstrap = 10
        cov = bs.cov(func=self.func, reps=num_bootstrap, recenter=False)
        bs.reset()

        results = np.zeros((num_bootstrap, 2))
        count = 0
        for data, _ in bs.bootstrap(num_bootstrap):
            results[count] = data[0].mean(axis=0)
            count += 1
        errors = results - self.x.mean(axis=0)
        direct_cov = errors.T.dot(errors) / num_bootstrap
        assert_allclose(cov, direct_cov)

        bs.reset()
        cov = bs.cov(func=self.func, recenter=True, reps=num_bootstrap)
        errors = results - results.mean(axis=0)
        direct_cov = errors.T.dot(errors) / num_bootstrap
        assert_allclose(cov, direct_cov)

        bs = IIDBootstrap(self.x_df)
        cov = bs.cov(func=self.func, reps=num_bootstrap, recenter=False)
        bs.reset()
        var = bs.var(func=self.func, reps=num_bootstrap, recenter=False)
        bs.reset()
        results = np.zeros((num_bootstrap, 2))
        count = 0
        for data, _ in bs.bootstrap(num_bootstrap):
            results[count] = data[0].mean(axis=0)
            count += 1
        errors = results - self.x.mean(axis=0)
        direct_cov = errors.T.dot(errors) / num_bootstrap
        assert_allclose(cov, direct_cov)
        assert_allclose(var, np.diag(direct_cov))

        bs.reset()
        cov = bs.cov(func=self.func, recenter=True, reps=num_bootstrap)
        errors = results - results.mean(axis=0)
        direct_cov = errors.T.dot(errors) / num_bootstrap
        assert_allclose(cov, direct_cov)

    def test_conf_int_basic(self):
        num_bootstrap = 200
        bs = IIDBootstrap(self.x)

        ci = bs.conf_int(self.func, reps=num_bootstrap, size=0.90, method='basic')
        bs.reset()
        ci_u = bs.conf_int(self.func, tail='upper', reps=num_bootstrap, size=0.95,
                           method='basic')
        bs.reset()
        ci_l = bs.conf_int(self.func, tail='lower', reps=num_bootstrap, size=0.95,
                           method='basic')
        bs.reset()
        results = np.zeros((num_bootstrap, 2))
        count = 0
        for pos, _ in bs.bootstrap(num_bootstrap):
            results[count] = self.func(*pos)
            count += 1
        mu = self.func(self.x)
        upper = mu + (mu - np.percentile(results, 5, axis=0))
        lower = mu + (mu - np.percentile(results, 95, axis=0))

        assert_allclose(lower, ci[0, :])
        assert_allclose(upper, ci[1, :])

        assert_allclose(ci[1, :], ci_u[1, :])
        assert_allclose(ci[0, :], ci_l[0, :])
        inf = np.empty_like(ci_l[0, :])
        inf.fill(np.inf)
        assert_equal(inf, ci_l[1, :])
        assert_equal(-1 * inf, ci_u[0, :])

    def test_conf_int_percentile(self):
        num_bootstrap = 200
        bs = IIDBootstrap(self.x)

        ci = bs.conf_int(self.func, reps=num_bootstrap, size=0.90,
                         method='percentile')
        bs.reset()
        ci_u = bs.conf_int(self.func, tail='upper', reps=num_bootstrap, size=0.95,
                           method='percentile')
        bs.reset()
        ci_l = bs.conf_int(self.func, tail='lower', reps=num_bootstrap, size=0.95,
                           method='percentile')
        bs.reset()
        results = np.zeros((num_bootstrap, 2))
        count = 0
        for pos, _ in bs.bootstrap(num_bootstrap):
            results[count] = self.func(*pos)
            count += 1

        upper = np.percentile(results, 95, axis=0)
        lower = np.percentile(results, 5, axis=0)

        assert_allclose(lower, ci[0, :])
        assert_allclose(upper, ci[1, :])

        assert_allclose(ci[1, :], ci_u[1, :])
        assert_allclose(ci[0, :], ci_l[0, :])
        inf = np.empty_like(ci_l[0, :])
        inf.fill(np.inf)
        assert_equal(inf, ci_l[1, :])
        assert_equal(-1 * inf, ci_u[0, :])

    def test_conf_int_norm(self):
        num_bootstrap = 200
        bs = IIDBootstrap(self.x)

        ci = bs.conf_int(self.func, reps=num_bootstrap, size=0.90,
                         method='norm')
        bs.reset()
        ci_u = bs.conf_int(self.func, tail='upper', reps=num_bootstrap, size=0.95,
                           method='var')
        bs.reset()
        ci_l = bs.conf_int(self.func, tail='lower', reps=num_bootstrap, size=0.95,
                           method='cov')
        bs.reset()
        cov = bs.cov(self.func, reps=num_bootstrap)
        mu = self.func(self.x)
        std_err = np.sqrt(np.diag(cov))
        upper = mu + stats.norm.ppf(0.95) * std_err
        lower = mu + stats.norm.ppf(0.05) * std_err
        assert_allclose(lower, ci[0, :])
        assert_allclose(upper, ci[1, :])

        assert_allclose(ci[1, :], ci_u[1, :])
        assert_allclose(ci[0, :], ci_l[0, :])
        inf = np.empty_like(ci_l[0, :])
        inf.fill(np.inf)
        assert_equal(inf, ci_l[1, :])
        assert_equal(-1 * inf, ci_u[0, :])

    def test_reuse(self):
        num_bootstrap = 100
        bs = IIDBootstrap(self.x)

        ci = bs.conf_int(self.func, reps=num_bootstrap)
        old_results = bs._results.copy()
        ci_reuse = bs.conf_int(self.func, reps=num_bootstrap, reuse=True)
        results = bs._results
        assert_equal(results, old_results)
        assert_equal(ci, ci_reuse)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", RuntimeWarning)
            warnings.simplefilter("always")
            bs.conf_int(self.func, tail='lower', reps=num_bootstrap // 2, reuse=True)
            assert_equal(len(w), 1)

    def test_studentized(self):
        num_bootstrap = 20
        bs = IIDBootstrap(self.x)
        bs.seed(23456)

        def std_err_func(mu, y):
            errors = y - mu
            var = (errors ** 2.0).mean(axis=0)
            return np.sqrt(var / y.shape[0])

        ci = bs.conf_int(self.func, reps=num_bootstrap, method='studentized',
                         std_err_func=std_err_func)
        bs.reset()
        base = self.func(self.x)
        results = np.zeros((num_bootstrap, 2))
        stud_results = np.zeros((num_bootstrap, 2))
        count = 0
        for pos, _ in bs.bootstrap(reps=num_bootstrap):
            results[count] = self.func(*pos)
            std_err = std_err_func(results[count], *pos)
            stud_results[count] = (results[count] - base) / std_err
            count += 1

        assert_allclose(results, bs._results)
        assert_allclose(stud_results, bs._studentized_results)
        errors = results - results.mean(0)
        std_err = np.sqrt(np.mean(errors ** 2.0, axis=0))
        ci_direct = np.zeros((2, 2))
        for i in range(2):
            ci_direct[0, i] = base[i] - std_err[i] * np.percentile(
                stud_results[:, i], 97.5)
            ci_direct[1, i] = base[i] - std_err[i] * np.percentile(
                stud_results[:, i], 2.5)
        assert_allclose(ci, ci_direct)

        bs.reset()
        ci = bs.conf_int(self.func, reps=num_bootstrap, method='studentized',
                         studentize_reps=50)

        bs.reset()
        base = self.func(self.x)
        results = np.zeros((num_bootstrap, 2))
        stud_results = np.zeros((num_bootstrap, 2))
        count = 0
        for pos, _ in bs.bootstrap(reps=num_bootstrap):
            results[count] = self.func(*pos)
            inner_bs = IIDBootstrap(*pos)
            seed = bs.random_state.randint(2 ** 31 - 1)
            inner_bs.seed(seed)
            cov = inner_bs.cov(self.func, reps=50)
            std_err = np.sqrt(np.diag(cov))
            stud_results[count] = (results[count] - base) / std_err
            count += 1

        assert_allclose(results, bs._results)
        assert_allclose(stud_results, bs._studentized_results)
        errors = results - results.mean(0)
        std_err = np.sqrt(np.mean(errors ** 2.0, axis=0))

        ci_direct = np.zeros((2, 2))
        for i in range(2):
            ci_direct[0, i] = base[i] - std_err[i] * np.percentile(
                stud_results[:, i], 97.5)
            ci_direct[1, i] = base[i] - std_err[i] * np.percentile(
                stud_results[:, i], 2.5)
        assert_allclose(ci, ci_direct)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bs.conf_int(self.func, reps=num_bootstrap, method='studentized',
                        std_err_func=std_err_func, reuse=True)
            assert_equal(len(w), 1)

    def test_conf_int_bias_corrected(self):
        num_bootstrap = 20
        bs = IIDBootstrap(self.x)
        bs.seed(23456)

        ci = bs.conf_int(self.func, reps=num_bootstrap, method='bc')
        bs.reset()
        ci_db = bs.conf_int(self.func, reps=num_bootstrap, method='debiased')
        assert_equal(ci, ci_db)
        base, results = bs._base, bs._results
        p = np.zeros(2)
        p[0] = np.mean(results[:, 0] < base[0])
        p[1] = np.mean(results[:, 1] < base[1])
        b = stats.norm.ppf(p)
        q = stats.norm.ppf(np.array([0.025, 0.975]))
        q = q[:, None]
        percentiles = 100 * stats.norm.cdf(2 * b + q)

        ci = np.zeros((2, 2))
        for i in range(2):
            ci[i] = np.percentile(results[:, i], list(percentiles[:, i]))
        ci = ci.T
        assert_allclose(ci_db, ci)

    def test_conf_int_bca_scaler(self):
        num_bootstrap = 100
        bs = IIDBootstrap(self.y)
        bs.seed(23456)

        ci = bs.conf_int(np.mean, reps=num_bootstrap, method='bca')
        msg = 'conf_int(method=\'bca\') scalar input regression. Ensure ' \
              'output is at least 1D with numpy.atleast_1d().'
        assert ci.shape == (2, 1), msg

    def test_conf_int_parametric(self):
        def param_func(x, params=None, state=None):
            if state is not None:
                mu = params
                e = state.standard_normal(x.shape)
                return (mu + e).mean(0)
            else:
                return x.mean(0)

        def semi_func(x, params=None):
            if params is not None:
                mu = params
                e = x - mu
                return (mu + e).mean(0)
            else:
                return x.mean(0)

        reps = 100
        bs = IIDBootstrap(self.x)
        bs.seed(23456)

        ci = bs.conf_int(func=param_func, reps=reps, sampling='parametric')
        assert len(ci) == 2
        assert np.all(ci[0] < ci[1])
        bs.reset()
        results = np.zeros((reps, 2))
        count = 0
        mu = self.x.mean(0)
        for pos, _ in bs.bootstrap(100):
            results[count] = param_func(*pos, params=mu,
                                        state=bs.random_state)
            count += 1
        assert_equal(bs._results, results)

        bs.reset()
        ci = bs.conf_int(func=semi_func, reps=100, sampling='semi')
        assert len(ci) == 2
        assert np.all(ci[0] < ci[1])
        bs.reset()
        results = np.zeros((reps, 2))
        count = 0
        for pos, _ in bs.bootstrap(100):
            results[count] = semi_func(*pos, params=mu)
            count += 1
        assert_allclose(bs._results, results)

    def test_extra_kwargs(self):
        extra_kwargs = {'axis': 0}
        bs = IIDBootstrap(self.x)
        bs.seed(23456)
        num_bootstrap = 100

        bs.cov(self.func, reps=num_bootstrap, extra_kwargs=extra_kwargs)

        bs = IIDBootstrap(axis=self.x)
        bs.seed(23456)
        with pytest.raises(ValueError):
            bs.cov(self.func, reps=num_bootstrap, extra_kwargs=extra_kwargs)

    def test_jackknife(self):
        x = self.x
        results = _loo_jackknife(self.func, len(x), (x,), {})

        direct_results = np.zeros_like(x)
        for i in range(len(x)):
            if i == 0:
                y = x[1:]
            elif i == (len(x) - 1):
                y = x[:-1]
            else:
                temp = list(x[:i])
                temp.extend(list(x[i + 1:]))
                y = np.array(temp)
            direct_results[i] = self.func(y)
        assert_allclose(direct_results, results)

        x = self.x_df
        results_df = _loo_jackknife(self.func, len(x), (x,), {})
        assert_equal(results, results_df)

        y = self.y
        results = _loo_jackknife(self.func, len(y), (y,), {})

        direct_results = np.zeros_like(y)
        for i in range(len(y)):
            if i == 0:
                z = y[1:]
            elif i == (len(y) - 1):
                z = y[:-1]
            else:
                temp = list(y[:i])
                temp.extend(list(y[i + 1:]))
                z = np.array(temp)
            direct_results[i] = self.func(z)
        assert_allclose(direct_results, results)

        y = self.y_series
        results_series = _loo_jackknife(self.func, len(y), (y,), {})
        assert_allclose(results, results_series)

    def test_bca(self):
        num_bootstrap = 20
        bs = IIDBootstrap(self.x)
        bs.seed(23456)

        ci_direct = bs.conf_int(self.func, reps=num_bootstrap, method='bca')
        bs.reset()
        base, results = bs._base, bs._results
        p = np.zeros(2)
        p[0] = np.mean(results[:, 0] < base[0])
        p[1] = np.mean(results[:, 1] < base[1])
        b = stats.norm.ppf(p)
        b = b[:, None]
        q = stats.norm.ppf(np.array([0.025, 0.975]))

        base = self.func(self.x)
        nobs = self.x.shape[0]
        jk = _loo_jackknife(self.func, nobs, [self.x], {})
        u = (nobs - 1) * (jk - jk.mean())
        u2 = np.sum(u * u, 0)
        u3 = np.sum(u * u * u, 0)
        a = u3 / (6.0 * (u2 ** 1.5))
        a = a[:, None]
        percentiles = 100 * stats.norm.cdf(b + (b + q) / (1 - a * (b + q)))

        ci = np.zeros((2, 2))
        for i in range(2):
            ci[i] = np.percentile(results[:, i], list(percentiles[i]))
        ci = ci.T
        assert_allclose(ci_direct, ci)

    def test_pandas_integer_index(self):
        x = self.x
        x_int = self.x_df.copy()
        x_int.index = 10 + np.arange(x.shape[0])
        bs = IIDBootstrap(x, x_int)
        bs.seed(23456)
        for pdata, _ in bs.bootstrap(10):
            assert_equal(pdata[0], pdata[1].values)

    def test_apply(self):
        bs = IIDBootstrap(self.x)
        bs.seed(23456)

        results = bs.apply(self.func, 1000)
        bs.reset(23456)
        direct_results = []
        for pos, _ in bs.bootstrap(1000):
            direct_results.append(self.func(*pos))
        direct_results = np.array(direct_results)
        assert_equal(results, direct_results)

    def test_apply_series(self):
        bs = IIDBootstrap(self.y_series)
        bs.seed(23456)

        results = bs.apply(self.func, 1000)
        bs.reset(23456)
        direct_results = []
        for pos, _ in bs.bootstrap(1000):
            direct_results.append(self.func(*pos))
        direct_results = np.array(direct_results)
        direct_results = direct_results[:, None]
        assert_equal(results, direct_results)

    def test_str(self):
        bs = IIDBootstrap(self.y_series)
        expected = 'IID Bootstrap(no. pos. inputs: 1, no. keyword inputs: 0)'
        assert_equal(str(bs), expected)
        expected = expected[:-1] + ', ID: ' + hex(id(bs)) + ')'
        assert_equal(bs.__repr__(), expected)
        expected = '<strong>IID Bootstrap</strong>(' + \
                   '<strong>no. pos. inputs</strong>: 1, ' + \
                   '<strong>no. keyword inputs</strong>: 0, ' + \
                   '<strong>ID</strong>: ' + hex(id(bs)) + ')'
        assert_equal(bs._repr_html(), expected)

        bs = StationaryBootstrap(10, self.y_series, self.x_df)
        expected = 'Stationary Bootstrap(block size: 10, no. pos. ' \
                   'inputs: 2, no. keyword inputs: 0)'
        assert_equal(str(bs), expected)
        expected = expected[:-1] + ', ID: ' + hex(id(bs)) + ')'
        assert_equal(bs.__repr__(), expected)

        bs = CircularBlockBootstrap(block_size=20, y=self.y_series,
                                    x=self.x_df)
        expected = 'Circular Block Bootstrap(block size: 20, no. pos. ' \
                   'inputs: 0, no. keyword inputs: 2)'
        assert_equal(str(bs), expected)
        expected = expected[:-1] + ', ID: ' + hex(id(bs)) + ')'
        assert_equal(bs.__repr__(), expected)
        expected = '<strong>Circular Block Bootstrap</strong>' + \
                   '(<strong>block size</strong>: 20, ' \
                   + '<strong>no. pos. inputs</strong>: 0, ' + \
                   '<strong>no. keyword inputs</strong>: 2,' + \
                   ' <strong>ID</strong>: ' + hex(id(bs)) + ')'
        assert_equal(bs._repr_html(), expected)

        bs = MovingBlockBootstrap(block_size=20, y=self.y_series,
                                  x=self.x_df)
        expected = 'Moving Block Bootstrap(block size: 20, no. pos. ' \
                   'inputs: 0, no. keyword inputs: 2)'
        assert_equal(str(bs), expected)
        expected = expected[:-1] + ', ID: ' + hex(id(bs)) + ')'
        assert_equal(bs.__repr__(), expected)
        expected = '<strong>Moving Block Bootstrap</strong>' + \
                   '(<strong>block size</strong>: 20, ' \
                   + '<strong>no. pos. inputs</strong>: 0, ' + \
                   '<strong>no. keyword inputs</strong>: 2,' + \
                   ' <strong>ID</strong>: ' + hex(id(bs)) + ')'
        assert_equal(bs._repr_html(), expected)

    def test_uneven_sampling(self):
        bs = MovingBlockBootstrap(block_size=31, y=self.y_series, x=self.x_df)
        for _, kw in bs.bootstrap(10):
            assert kw['y'].shape == self.y_series.shape
            assert kw['x'].shape == self.x_df.shape
        bs = CircularBlockBootstrap(block_size=31, y=self.y_series, x=self.x_df)
        for _, kw in bs.bootstrap(10):
            assert kw['y'].shape == self.y_series.shape
            assert kw['x'].shape == self.x_df.shape

    @pytest.mark.skipif(not HAS_EXTENSION, reason='Extension not built.')
    @pytest.mark.filterwarnings('ignore::arch.compat.numba.PerformanceWarning')
    def test_samplers(self):
        """
        Test all three implementations are identical
        """
        indices = np.array(self.rng.randint(0, 1000, 1000), dtype=np.int64)
        u = self.rng.random_sample(1000)
        p = 0.1
        indices_orig = indices.copy()

        numba = stationary_bootstrap_sample(indices, u, p)
        indices = indices_orig.copy()
        python = stationary_bootstrap_sample_python(indices, u, p)
        indices = indices_orig.copy()
        cython = stationary_bootstrap_sample_cython(indices, u, p)
        assert_equal(numba, cython)
        assert_equal(numba, python)


def test_pass_random_state():
    x = np.arange(1000)
    rs = RandomState(0)
    IIDBootstrap(x, random_state=rs)

    with pytest.raises(TypeError):
        IIDBootstrap(x, random_state=0)


def test_iid_unequal_equiv():
    rs = RandomState(0)
    x = rs.randn(500)
    rs1 = RandomState(0)
    bs1 = IIDBootstrap(x, random_state=rs1)

    rs2 = RandomState(0)
    bs2 = IndependentSamplesBootstrap(x, random_state=rs2)

    v1 = bs1.var(np.mean)
    v2 = bs2.var(np.mean)
    assert_allclose(v1, v2)


def test_unequal_bs():
    def mean_diff(*args):
        return args[0].mean() - args[1].mean()

    rs = RandomState(0)
    x = rs.randn(800)
    y = rs.randn(200)

    bs = IndependentSamplesBootstrap(x, y, random_state=rs)
    variance = bs.var(mean_diff)
    assert variance > 0
    ci = bs.conf_int(mean_diff)
    assert ci[0] < ci[1]
    applied = bs.apply(mean_diff, 1000)
    assert len(applied) == 1000

    x = pd.Series(x)
    y = pd.Series(y)
    bs = IndependentSamplesBootstrap(x, y)
    variance = bs.var(mean_diff)
    assert variance > 0


def test_unequal_bs_kwargs():
    def mean_diff(x, y):
        return x.mean() - y.mean()

    rs = RandomState(0)
    x = rs.randn(800)
    y = rs.randn(200)

    bs = IndependentSamplesBootstrap(x=x, y=y, random_state=rs)
    variance = bs.var(mean_diff)
    assert variance > 0
    ci = bs.conf_int(mean_diff)
    assert ci[0] < ci[1]
    applied = bs.apply(mean_diff, 1000)

    x = pd.Series(x)
    y = pd.Series(y)
    bs = IndependentSamplesBootstrap(x=x, y=y, random_state=rs)
    variance = bs.var(mean_diff)
    assert variance > 0

    assert len(applied) == 1000


def test_unequal_reset():
    def mean_diff(*args):
        return args[0].mean() - args[1].mean()

    rs = RandomState(0)
    x = rs.randn(800)
    y = rs.randn(200)
    orig_state = rs.get_state()
    bs = IndependentSamplesBootstrap(x, y, random_state=rs)
    variance = bs.var(mean_diff)
    assert variance > 0
    bs.reset()
    state = bs.get_state()
    assert_equal(state[1], orig_state[1])

    bs = IndependentSamplesBootstrap(x, y)
    bs.seed(0)
    orig_state = bs.get_state()
    bs.var(mean_diff)
    bs.reset(use_seed=True)
    state = bs.get_state()
    assert_equal(state[1], orig_state[1])
