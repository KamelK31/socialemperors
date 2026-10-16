package battle
{
   import battle.projectiles.ProjectileDefinition;
   import battle.projectiles.ProjectilesNames;
   import caurina.transitions.*;
   import core.*;
   import core.isoengine.IsoFightingElement;
   import core.statics.*;
   import flash.display.*;
   import flash.events.*;
   import flash.geom.Point;
   import flash.net.*;
   import flash.system.*;
   import flash.text.*;
   import flash.utils.Timer;
   import flash.utils.getDefinitionByName;
   import managers.Projectiles;
   
   public class FXArrowAnimation extends MovieClip
   {
      
      private var xInit:Number = 0;
      
      private var yInit:Number = 0;
      
      public var xFinish:Number = 0;
      
      public var yFinish:Number = 0;
      
      private var xMiddle:Number = 0;
      
      private var yMiddle:Number = 0;
      
      private var fxTime:Number = 1;
      
      private var RtoA:Number = 57.2957795131;
      
      private var rot2:Number;
      
      private var factorTime:Number = 1000;
      
      private var tipoDisparo:String = "";
      
      private var callBackFinish:Function;
      
      public var disparo_mc:MovieClip;
      
      public var uTargetElement:*;
      
      private var uiAttack:uint;
      
      private var attacker:*;
      
      public var splashDistance:Number = 40;
      
      public var shootBeam:Boolean = false;
      
      public var beamDuration:Number = 0;
      
      public var finalXDest:int;
      
      public var finalYDest:int;
      
      public var targetFrame:int = -1;
      
      public function FXArrowAnimation(param1:*, param2:Function, param3:Number, param4:Number, param5:Number, param6:Number, param7:*, param8:uint, param9:*, param10:Boolean = false, param11:Number = 0.25, param12:Number = -1)
      {
         var _loc13_:Class = null;
         var _loc14_:String = null;
         super();
         if(param12 != -1)
         {
            this.factorTime = param12;
         }
         if(param1 is ProjectileDefinition)
         {
            _loc14_ = (param1 as ProjectileDefinition).projectileID;
            this.disparo_mc = projectileClip(_loc14_);
            this.tipoDisparo = _loc14_;
         }
         else if(param1 is String)
         {
            this.tipoDisparo = param1;
            if(param1 == "")
            {
               this.disparo_mc = new MovieClip();
            }
            else
            {
               this.disparo_mc = projectileClip(param1);
            }
         }
         else
         {
            this.disparo_mc = new MovieClip();
         }
         addChild(this.disparo_mc);
         this.callBackFinish = param2;
         this.xFinish = param5;
         this.yFinish = param6;
         this.finalXDest = param5;
         this.finalYDest = param6;
         this.uTargetElement = param7;
         this.uiAttack = param8;
         this.attacker = param9;
         this.x = param3;
         this.y = param4;
         this.shootBeam = param10;
         this.beamDuration = param11;
         this.xFinish -= x;
         this.yFinish -= y;
         this.xFinish += GameStatic.randomRange(-15,15);
         this.yFinish += GameStatic.randomRange(-10,10);
         if(this.shootBeam)
         {
            this.initBeam();
         }
         else
         {
            this.initAnimation();
         }
         this.checkRotation();
      }
      
      // A projectile whose file was never preloaded (e.g. p.lightning of the Mythological and Lightning
      // towers) used to throw here: the tower never fired and the rest of the game's frame was skipped.
      // Now the file is loaded for the next shots and this shot uses the arrow (the damage is the same).
      private static function projectileClip(param1:String) : *
      {
         var cls:Class = null;
         try
         {
            cls = getDefinitionByName(param1) as Class;
         }
         catch(e:Error)
         {
            cls = null;
            try
            {
               Projectiles.api.loadAsset(param1);
            }
            catch(e2:Error)
            {
            }
            try
            {
               cls = getDefinitionByName(ProjectilesNames.P_ARROW) as Class;
            }
            catch(e3:Error)
            {
               cls = null;
            }
         }
         if(cls == null)
         {
            return new MovieClip();
         }
         return new cls();
      }
      
      public function checkRotation() : void
      {
         var _loc1_:MovieClip = null;
         var _loc2_:int = 0;
         if(this.tipoDisparo == ProjectilesNames.P_GHOSTLY_SKULL || this.tipoDisparo == ProjectilesNames.P_CENTAURO_KNIFE)
         {
            _loc1_ = MovieClip(this.disparo_mc.getChildAt(0));
            if(_loc1_ != null)
            {
               _loc2_ = int(this.attacker.currentDirection);
               if(_loc2_ > 5)
               {
                  _loc2_ -= 4;
                  _loc1_.scaleX = -_loc1_.scaleX;
               }
               _loc1_.gotoAndStop(_loc2_);
            }
         }
      }
      
      public function initBeam() : void
      {
         var _loc3_:MovieClip = null;
         var _loc4_:Point = null;
         if(this.xFinish == 0 && this.yFinish == 0)
         {
            return;
         }
         var _loc1_:Number = Math.sqrt(this.xFinish * this.xFinish + this.yFinish * this.yFinish);
         var _loc2_:Number = Math.atan2(this.yFinish,this.xFinish) * this.RtoA;
         this.disparo_mc.width = _loc1_;
         if(this.tipoDisparo == ProjectilesNames.P_LIGHT_BEAM)
         {
            _loc3_ = new puntaRayoMC();
            this.disparo_mc.beam.addChild(_loc3_);
         }
         else if(this.tipoDisparo == ProjectilesNames.P_PUNK_BEAM)
         {
            _loc3_ = new puntaRayo2MC();
            this.disparo_mc.beam.addChild(_loc3_);
         }
         this.disparo_mc.rotation = _loc2_;
         if(this.tipoDisparo == ProjectilesNames.P_FIREBEAM_BAHAMUT)
         {
            _loc3_ = new FuegoBahamutMC();
            _loc4_ = this.disparo_mc.beam.localToGlobal(new Point());
            _loc4_ = this.globalToLocal(_loc4_);
            _loc3_.x = _loc4_.x;
            _loc3_.y = _loc4_.y;
            this.addChild(_loc3_);
         }
         var _loc5_:Timer = new Timer(this.beamDuration * 1000,1);
         _loc5_.start();
         _loc5_.addEventListener(TimerEvent.TIMER_COMPLETE,this.beamEnd);
         if(this.attacker.delegate != null)
         {
            this.attacker.delegate.onInitBeam(this.attacker,this.uTargetElement,this);
         }
      }
      
      private function beamEffect() : void
      {
      }
      
      private function beamEnd(param1:TimerEvent) : void
      {
         this.doFinish();
      }
      
      public function initAnimation() : void
      {
         var _loc1_:Number = NaN;
         var _loc4_:Number = NaN;
         var _loc7_:Number = NaN;
         this.disparo_mc.x = this.xInit;
         this.disparo_mc.y = this.yInit;
         var _loc2_:Number = Math.abs(this.xInit - this.xFinish);
         var _loc3_:Number = Math.abs(this.yInit - this.yFinish);
         var _loc5_:Number = Math.round(Math.sqrt(_loc2_ * _loc2_ + _loc3_ * _loc3_));
         this.fxTime = Math.round(_loc5_ / this.factorTime * 100) / 100;
         if(this.xInit > this.xFinish)
         {
            this.xMiddle = this.xInit - _loc2_ / 2;
            _loc4_ = -90;
         }
         else
         {
            this.xMiddle = this.xInit + _loc2_ / 2;
            _loc4_ = 90;
         }
         if(this.yInit > this.yFinish)
         {
            this.yMiddle = this.yFinish - Math.round(_loc2_ / 20);
         }
         else
         {
            this.yMiddle = this.yInit - Math.round(_loc2_ / 20);
         }
         _loc1_ = Math.atan2(this.xInit - this.xMiddle,this.yInit - this.yMiddle);
         var _loc6_:Number = -(_loc1_ * this.RtoA);
         this.disparo_mc.rotation = _loc6_;
         _loc1_ = Math.atan2(this.xMiddle - this.xFinish,this.yMiddle - this.yFinish);
         this.rot2 = -(_loc1_ * this.RtoA);
         if(_loc2_ < 50)
         {
            _loc4_ = _loc6_;
            this.rot2 = _loc6_;
         }
         if(_loc5_ < 300 || this.tipoDisparo == ProjectilesNames.P_LIGHTNING || this.tipoDisparo == ProjectilesNames.P_HOJARADA || this.tipoDisparo == ProjectilesNames.P_FUEGO_GIGANTE || this.tipoDisparo == ProjectilesNames.P_ZOMBIE_HEAD || this.tipoDisparo == ProjectilesNames.P_GHOSTLY_SKULL || this.tipoDisparo == ProjectilesNames.P_CENTAURO_KNIFE || this.tipoDisparo == ProjectilesNames.P_GOLDEN_DRAGON || this.tipoDisparo == ProjectilesNames.P_PUNK_ENERGY_BALL || this.tipoDisparo == ProjectilesNames.P_CRYSTAL_BALL || this.attacker.buildingReference.building.id == Constants.ID_UNIT_EL_ROYAL_ARCHER || this.attacker.buildingReference.building.id == Constants.ID_UNIT_EL_BALLISTA || this.attacker.buildingReference.building.id == Constants.ID_UNIT_DRAGGY || this.attacker.buildingReference.building.id == Constants.ID_UNIT_DRAGGY_RED_EVIL || this.attacker.buildingReference.building.id == Constants.ID_UNIT_DRAGGY_BLUE_EVIL || this.attacker.buildingReference.building.id == Constants.ID_UNIT_MERLIN_RED || this
         .attacker.buildingReference.building.id == Constants.ID_UNIT_MERLIN_RED_EVIL || this.attacker.buildingReference.building.id == Constants.ID_UNIT_MERLIN_EARTH || this.attacker.buildingReference.building.id == Constants.ID_UNIT_MERLIN_EARTH_EVIL || this.attacker.buildingReference.building.id == Constants.ID_UNIT_MERLIN_BLUE_EVIL || this.attacker.buildingReference.building.id == Constants.ID_UNIT_SAYAN_DRAGON || this.attacker.buildingReference.building.id == Constants.ID_UNIT_DRAGGY_GREEN || this.attacker.buildingReference.building.id == Constants.ID_UNIT_GOLDEN_DRAGGY || this.attacker.buildingReference.building.id == Constants.ID_UNIT_GOLDEN_DRAGON || this.attacker.buildingReference.building.id == Constants.ID_UNIT_DRACULA || this.attacker.buildingReference.building.id == Constants.ID_UNIT_NINJA || this.attacker.buildingReference.building.id == Constants.ID_UNIT_BLACK_DRAGGY || this.attacker.buildingReference.building.id == Constants.ID_UNIT_BLACK_DRAGON || this.attacker.buildingReference
         .building.id == Constants.ID_UNIT_PHOENIX || this.attacker.buildingReference.building.id == Constants.ID_UNIT_MEDUSA || this.attacker.buildingReference.building.id == Constants.ID_UNIT_CERBERUS || this.attacker.buildingReference.building.id == Constants.ID_UNIT_DRAGGY_PUNKY || this.attacker.buildingReference.building.id == Constants.ID_UNIT_ANTIMATTER_WIZARD || this.attacker.buildingReference.building.id == Constants.ID_UNIT_GOD_POSEIDON || this.attacker.buildingReference.building.id == Constants.ID_UNIT_GOD_ZEUS || this.attacker.buildingReference.building.id == Constants.ID_UNIT_TITAN_HYDROS || this.attacker.buildingReference.building.id == Constants.ID_UNIT_BLUE_PHOENIX || this.attacker.buildingReference.building.id == Constants.ID_UNIT_PHOENIX_GREEN || this.attacker.buildingReference.building.id == Constants.ID_UNIT_HORNED_DRAGON || this.attacker.buildingReference.building.id == Constants.ID_UNIT_FURIOUS_BULL_DRAGON || this.attacker.buildingReference.building.id == Constants.ID_UNIT_BLUE_PHOENIX || this
         .attacker.buildingReference.building.id == Constants.ID_UNIT_MANTICORA || this.attacker.buildingReference.building.id == Constants.ID_UNIT_NECRO_HORSEMAN || this.attacker.buildingReference.building.id == Constants.ID_UNIT_DEATH_DRAGON || this.attacker.buildingReference.building.id == Constants.ID_UNIT_BAHAMUT_DRAGGY || this.attacker.buildingReference.building.id == Constants.ID_UNIT_RED_BAHAMUT_DRAGGY || this.attacker.buildingReference.building.id == Constants.ID_UNIT_RED_BAHAMUT_DRAGON || this.attacker.buildingReference.building.id == Constants.ID_UNIT_RED_BAHAMUT_DJ || this.attacker.buildingReference.building.id == Constants.ID_UNIT_VULCANO_DRAGGY || this.attacker.buildingReference.building.id == Constants.ID_UNIT_SNAKE_DRAGGY || this.attacker.buildingReference.building.id == Constants.ID_UNIT_INFRAWORLD_COLLOSUS)
         {
            _loc7_ = Math.atan2(this.xInit - this.xFinish,this.yInit - this.yFinish);
            _loc7_ = -(_loc7_ * this.RtoA);
            this.disparo_mc.rotation = _loc7_;
            if(this.tipoDisparo == ProjectilesNames.P_GHOSTLY_SKULL || this.tipoDisparo == ProjectilesNames.P_SHURIKEN.toString() || this.tipoDisparo == ProjectilesNames.P_CENTAURO_KNIFE)
            {
               this.disparo_mc.rotation = 0;
               _loc4_ = 0;
               this.rot2 = 0;
            }
            Tweener.addTween(this.disparo_mc,{
               "x":this.xFinish,
               "time":this.fxTime,
               "transition":"linear"
            });
            Tweener.addTween(this.disparo_mc,{
               "y":this.yFinish,
               "time":this.fxTime,
               "transition":"linear",
               "onComplete":this.doFinish
            });
         }
         else
         {
            Tweener.addTween(this.disparo_mc,{
               "x":this.xMiddle,
               "rotation":_loc4_,
               "time":this.fxTime,
               "transition":"linear"
            });
            Tweener.addTween(this.disparo_mc,{
               "y":this.yMiddle,
               "time":this.fxTime,
               "transition":"easeOutCirc",
               "onComplete":this.doPart2
            });
         }
      }
      
      public function doPart2() : void
      {
         Tweener.addTween(this.disparo_mc,{
            "x":this.xFinish,
            "rotation":this.rot2,
            "time":this.fxTime * 0.6,
            "transition":"linear"
         });
         Tweener.addTween(this.disparo_mc,{
            "y":this.yFinish,
            "time":this.fxTime * 0.6,
            "transition":"easeInCirc",
            "onComplete":this.doFinish
         });
      }
      
      public function doFinish() : void
      {
         if(this.attacker.delegate != null)
         {
            this.attacker.delegate.onEndProjectile(IsoFightingElement(this.attacker),this.uTargetElement,this);
         }
         if(this.callBackFinish != null)
         {
            this.callBackFinish(this,this.uTargetElement,this.uiAttack,this.attacker);
         }
      }
      
      public function get type() : String
      {
         return this.tipoDisparo;
      }
   }
}

