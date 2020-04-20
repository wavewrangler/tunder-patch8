from selfdrive.car import apply_toyota_steer_torque_limits
from selfdrive.car.chrysler.chryslercan import create_lkas_command, create_wheel_buttons
from selfdrive.car.chrysler.values import CAR, DBC, SteerLimitParams
from opendbc.can.packer import CANPacker

class CarController():
  def __init__(self, dbc_name, CP, VM):
    self.braking = False
    self.apply_steer_last = 0
    self.hud_count = 0
    self.car_fingerprint = CP.carFingerprint
    self.alert_active = False
    self.gone_fast_yet = False
    self.steer_rate_limited = False

    self.packer = CANPacker(DBC[CP.carFingerprint]['pt'])


  def update(self, enabled, CS, frame, actuators, pcm_cancel_cmd): #TODO hud_alert
    # *** compute control surfaces ***
    # steer torque
    new_steer = actuators.steer * SteerLimitParams.STEER_MAX
    apply_steer = apply_toyota_steer_torque_limits(new_steer, self.apply_steer_last,
                                                   CS.out.steeringTorqueEps, SteerLimitParams)
    self.steer_rate_limited = new_steer != apply_steer

    moving_fast = CS.out.vEgo > CS.CP.minSteerSpeed  # for status message
    if CS.out.vEgo > (CS.CP.minSteerSpeed - 0.5):  # for command high bit
      self.gone_fast_yet = True
  #  elif self.car_fingerprint in (CAR.PACIFICA_2019_HYBRID, CAR.JEEP_CHEROKEE_2019):
  #    if CS.out.vEgo < (CS.CP.minSteerSpeed - 3.0):
  #      self.gone_fast_yet = False  # < 14.5m/s stock turns off this bit, but fine down to 13.5
    lkas_active = moving_fast and enabled

    if not lkas_active:
      apply_steer = 0

    self.apply_steer_last = apply_steer

    can_sends = []

    #*** control msgs ***

    if pcm_cancel_cmd:
      new_msg = create_wheel_buttons(CS.frame_23b)
      can_sends.append(new_msg)

    # LKAS_HEARTBIT is forwarded by Panda so no need to send it here.
    # frame is 100Hz (0.01s period)
    #TODO LKAS_HUD
  #  if (self.ccframe % 25 == 0):  # 0.25s period
  #    if (CS.lkas_car_model != -1):
  #      new_msg = create_lkas_hud(
  #          self.packer, CS.out.gearShifter, lkas_active, hud_alert,
  #          self.hud_count, CS.lkas_car_model)
  #      can_sends.append(new_msg)
  #      self.hud_count += 1

    new_msg = create_lkas_command(self.packer, int(apply_steer), self.gone_fast_yet, frame)
    can_sends.append(new_msg)

    return can_sends
