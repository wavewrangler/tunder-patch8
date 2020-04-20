from cereal import car
from opendbc.can.parser import CANParser
#from opendbc.can.can_define import CANDefine
from selfdrive.config import Conversions as CV
from selfdrive.car.interfaces import CarStateBase
from selfdrive.car.chrysler.values import DBC, STEER_THRESHOLD


class CarState(CarStateBase):
  def __init__(self, CP):
    super().__init__(CP)
    #can_define = CANDefine(DBC[CP.carFingerprint]['pt'])
    #self.shifter_values = can_define.dv["GEAR"]['PRNDL']

  def update(self, cp, cp_cam):

    ret = car.CarState.new_message()

    ret.doorOpen = any([cp.vl["DOORS"]['DOOR_OPEN_FL'],
                        cp.vl["DOORS"]['DOOR_OPEN_FR'],
                        cp.vl["DOORS"]['DOOR_OPEN_RL'],
                        cp.vl["DOORS"]['DOOR_OPEN_RR']])
    ret.seatbeltUnlatched = cp.vl["SEATBELT_STATUS"]['SEATBELT_DRIVER_UNLATCHED'] == 1

    ret.brakePressed = cp.vl["BRAKE_2"]['BRAKE_HUMAN'] == 1 # human-only
    ret.brake = 0
    ret.brakeLights = bool(cp.vl["BRAKE_2"]['BRAKE_LIGHTS'])
    ret.gas = cp.vl["ACCEL_GAS"]['GAS_HUMAN']
    ret.gasPressed = ret.gas > 1e-5

    ret.espDisabled = (cp.vl["TRACTION_BUTTON"]['TRACTION_OFF'] == 1)

    ret.wheelSpeeds.fl = cp.vl['WHEEL_SPEEDS_FRONT']['WHEEL_SPEED_FL']
    ret.wheelSpeeds.rr = cp.vl['WHEEL_SPEEDS_REAR']['WHEEL_SPEED_RR']
    ret.wheelSpeeds.rl = cp.vl['WHEEL_SPEEDS_REAR']['WHEEL_SPEED_RL']
    ret.wheelSpeeds.fr = cp.vl['WHEEL_SPEEDS_FRONT']['WHEEL_SPEED_FR']
    ret.vEgoRaw = (cp.vl['WHEEL_SPEEDS_REAR']['WHEEL_SPEED_RL'] + cp.vl['WHEEL_SPEEDS_REAR']['WHEEL_SPEED_RR']) / 2.
    ret.vEgo, ret.aEgo = self.update_speed_kf(ret.vEgoRaw)
    ret.standstill = not ret.vEgoRaw > 0.001

    ret.leftBlinker = cp.vl["STEERING_LEVERS"]['TURN_SIGNALS'] == 1
    ret.rightBlinker = cp.vl["STEERING_LEVERS"]['TURN_SIGNALS'] == 2
    ret.steeringAngle = cp.vl["STEERING"]['STEER_ANGLE']
    ret.steeringRate = cp.vl["STEERING"]['STEERING_RATE']
    #ret.gearShifter = self.parse_gear_shifter(self.shifter_values.get(cp.vl['GEAR']['PRNDL'], None))
    ret.gearShifter = car.CarState.GearShifter.drive

    ret.cruiseState.enabled = cp.vl["ACC_1"]['ACC_STATE'] == 8  # ACC is green
    ret.cruiseState.available = cp.vl["ACC_1"]['ACC_STATE'] == 6  # ACC is white
    ret.cruiseState.speed = cp.vl["DASHBOARD"]['ACC_SPEED_CONFIG_KPH'] * CV.KPH_TO_MS

    ret.steeringTorque = cp.vl["EPS_STATUS"]["TORQUE_DRIVER"]
    ret.steeringTorqueEps = cp.vl["EPS_STATUS"]["TORQUE_MOTOR"]
    ret.steeringPressed = abs(ret.steeringTorque) > STEER_THRESHOLD
    steer_state = cp.vl["LKAS_COMMAND"]["LKAS_STATE"] == 2  #  LKAS is green
    self.steer_error = steer_state == 1 or (steer_state == 0 and ret.vEgo > self.CP.minSteerSpeed)

    ret.genericToggle = bool(cp.vl["STEERING_LEVERS"]['HIGH_BEAM_FLASH'])

    self.lkas_counter = cp_cam.vl["LKAS_COMMAND"]['COUNTER']
    self.frame_23b = int(cp.vl["WHEEL_BUTTONS"]['COUNTER'])

#    self.lkas_car_model = cp_cam.vl["LKAS_HUD"]['CAR_MODEL'] #TODO
    self.lkas_status_ok = cp_cam.vl["LKAS_HEARTBIT"]['LKAS_STATUS_OK']

    return ret

  @staticmethod
  def get_can_parser(CP):
    signals = [
      # sig_name, sig_address, default
      ("PRNDL", "GEAR", 0),
      ("DOOR_OPEN_FL", "DOORS", 0),
      ("DOOR_OPEN_FR", "DOORS", 0),
      ("DOOR_OPEN_RL", "DOORS", 0),
      ("DOOR_OPEN_RR", "DOORS", 0),
      ("BRAKE_HUMAN", "BRAKE_2", 0),
      ("BRAKE_LIGHTS", "BRAKE_2", 0),
      ("GAS_HUMAN", "ACCEL_GAS", 0),
      ("WHEEL_SPEED_FL", "WHEEL_SPEEDS_FRONT", 0),
      ("WHEEL_SPEED_RR", "WHEEL_SPEEDS_REAR", 0),
      ("WHEEL_SPEED_RL", "WHEEL_SPEEDS_REAR", 0),
      ("WHEEL_SPEED_FR", "WHEEL_SPEEDS_FRONT", 0),
      ("STEER_ANGLE", "STEERING", 0),
      ("STEERING_RATE", "STEERING", 0),
      ("TURN_SIGNALS", "STEERING_LEVERS", 0),
      ("ACC_STATE", "ACC_1", 0),
      ("HIGH_BEAM_FLASH", "STEERING_LEVERS", 0),
      ("ACC_SPEED_CONFIG_KPH", "DASHBOARD", 0), # find this #
      ("TORQUE_DRIVER", "EPS_STATUS", 0),
      ("TORQUE_MOTOR", "EPS_STATUS", 0), # find this, this is the bigger #
      ("LKAS_STATE", "LKAS_COMMAND", 1), 
      ("COUNTER", "LKAS_COMMAND", -1),
      ("TRACTION_OFF", "TRACTION_BUTTON", 0),
      ("SEATBELT_DRIVER_UNLATCHED", "SEATBELT_STATUS", 0),
      ("COUNTER", "WHEEL_BUTTONS", -1),
    ]

    checks = [
      # sig_address, frequency
      ("BRAKE_2", 50),
      ("EPS_STATUS", 100),
    #  ("SPEED_1", 100),
      ("WHEEL_SPEEDS_FRONT", 50),
      ("WHEEL_SPEEDS_REAR", 50),
      ("STEERING", 100),
      ("ACC_1", 50),
    ]

    return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, 0)

  @staticmethod
  def get_cam_can_parser(CP):
    signals = [
      # sig_name, sig_address, default
      ("COUNTER", "LKAS_COMMAND", -1),
    #  ("CAR_MODEL", "ACC_2", -1),
      ("LKAS_STATUS_OK", "LKAS_HEARTBIT", -1)
    ]
    checks = []

    return CANParser(DBC[CP.carFingerprint]['pt'], signals, checks, 2)
