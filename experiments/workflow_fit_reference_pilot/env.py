"""The one environment variable the synthetic fixture uses. Kept apart from the provider
module so the runner-side pipeline never imports provider code: the provider factory is
imported only by the boundary process."""

MODE_ENV = "WFRP_SYNTHETIC_MODE"  # ok | no_usage | raise:<method_id>

__all__ = ["MODE_ENV"]
