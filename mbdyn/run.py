#import packages

class MbdynAdapter:
	#initialize values
	
	def run(self):
		
		dt = interface.initialize()
		
		self.input.update_time_step(dt)
		self.mbdyn.initialize(case=self.mbdyn_prep.name)

		self.transform = Rotation()
		
		self.current_time_step = decimal.Decimal(str(dt))

		while interface.is_coupling_ongoing():
			
			if interface.is_action_required(
				    precice.action_write_iteration_checkpoint()):
				print("DUMMY: Writing iteration checkpoint")
				interface.mark_action_fulfilled(
				    precice.action_write_iteration_checkpoint())

			self.read_data.clear()
			self.force_tensor.clear()
			for i in range(self.patches):
				if interface.is_read_data_available():
					self.read_data.append(interface.read_block_vector_data(self.read_data_id[i], self.vertex_ids[i]))
				elif float(self.current_time_step) == float(decimal.Decimal(str(dt))):
					self.read_data.append(self.vertices[i]*0)
				else:
					exit("no data provided!")
				self.force_tensor.append(np.split(self.read_data[i],2)[0]*0) # prepare force_tensor for entries
				self.force_tensor[i] = np.concatenate((self.force_tensor[i],self.force_tensor[i][:2,:]*0)) # prepare force_tensor for entries, add empty anchor & ground force node
				for k,j in enumerate(np.split(self.read_data[i],2)):
					self.force_tensor[i] += np.concatenate((j,j[:2,:]*0)) # fill values into force_tensor, add empty anchor & ground force node
					
			#print(np.vstack(self.force_tensor))
			#import ipdb; ipdb.set_trace()
			self.mbdyn.set_forces(np.vstack(self.force_tensor))
			if self.mbdyn.solve(False):
				self.module_logger.debug('Something went wrong!')
				#MBDyn diverges
				break
				
			#nodes per patch
			npp = self.mbdyn.mesh.number_of_nodes()/self.patches
			if npp % 2 != 0 and npp % 1 != 0:
				exit("please check number of nodes / patches!")
			npp = int(npp)
			
			self.displacement_absolute.clear()
			self.displacement.clear()
			self.rotation.clear()
			self.message.clear()
			self.centre_of_gravity.clear()
			
			self.displacement_absolute_delta.clear()
			self.displacement_absolute_delta_str.clear()
			self.displacement_relative_delta.clear()
			self.rotation_absolute_delta.clear()
			self.rotation_absolute_delta_str.clear()
			self.mbdyn_mesh.clear()
			self.mbdyn_mesh_str.clear()
			self.nodes_absolute.clear()
			self.message.clear()
			
			for i in range(self.patches):
				
				# absolute = MBDyn base mesh as reference
				# absolute delta = MBDyn base mesh as reference, difference between current pos and base mesh
				#evaluate difference between initial mesh and current mesh
				#TODO: add clear commands above
				self.displacement_absolute_delta.append(self.mbdyn.get_absolute_displacement()[i*npp:(i+1)*npp,:]) 
				self.displacement_absolute_delta_str.append(np.array(np.array(self.displacement_absolute_delta[i],dtype='float16'),dtype='<U16'))
				self.rotation_absolute_delta.append(self.mbdyn.get_rotation()[i*npp:(i+1)*npp,:])
				self.rotation_absolute_delta_str.append(np.array(np.array(self.rotation_absolute_delta[i],dtype='float16'),dtype='<U16'))
				#TODO: change to old version with dynamicMeshDict
				self.mbdyn_mesh.append(self.mbdyn.mesh.nodes[i*npp:(i+1)*npp,:])
				self.mbdyn_mesh_str.append(np.array(np.array(self.mbdyn_mesh[i],dtype='float16'),dtype='<U16'))
				self.nodes_absolute.append(self.mbdyn.get_nodes()[i*npp:(i+1)*npp,:])
				self.nodes_absolute_str.append(np.array(np.array(self.nodes_absolute[i],dtype='float16'),dtype='<U16'))
			
			##############################
			### evaluate OpenFOAM data ###
			##############################
			for i in range(self.patches+1):
				#distinction between background and overset mesh
				if i == 0:
					#background mesh
					#import ipdb; ipdb.set_trace()
					self.message.append(';'.join(np.concatenate((self.displacement_absolute_delta_str[i][npp-1,:],
																	np.array(np.array(self.rotation_absolute_delta[i][npp-1,:]*0,dtype='float16'),dtype='<U16'),
																	np.array(np.array(self.mbdyn_mesh[i][npp-1,:]*0,dtype='float16'),dtype='<U16')))))
				else:
					#overset mesh
					self.message.append(';'.join(np.concatenate((self.displacement_absolute_delta_str[i-1][5,:],
																	self.rotation_absolute_delta_str[i-1][5,:],
																	self.mbdyn_mesh_str[i-1][5,:]))))
				print('Sending')
				print(self.message[i])
				print("iteration:" +str(i))
				self.exchange_socket[i].sendall(str.encode(self.message[i]))
					
				print('Sent')
				data = self.exchange_socket[i].recv(190) # 21 chars per message
				if str(data) == "b''":
					for j in range(self.patches+1):
						self.exchange_socket[j].close()
					exit("Client exit")
				split_string = str(data).split("\\n")
				data = split_string[0][2:]
				if str(data) == "exit":
					for j in range(self.patches+1):
						self.exchange_socket[j].close()
					exit("Client exit")
				print('Received')
				#print(repr(data))
			
			#############################
			### evaluate preCICE data ###
			#############################
			#time.sleep(2)
			for i in range(self.patches):				
				#transform rotor rotation of most deformed element
				
				#new anchor node positions - ground displacement_absolute_delta
				#TODO: npp-1,: instead npp-2,:
				#import ipdb; ipdb.set_trace()
				self.transform.importGrid(self.nodes_absolute[i][:npp-2,:]-self.displacement_absolute_delta[i][npp-1,:])
				XA, YA, ZA = self.transform.rotate(angle=-self.rotation_absolute_delta[i][npp-2,2],rot_point = np.array((0,0,0)))
				self.transform.importGrid(np.array((XA,YA,ZA)).T)
				#TODO: why npp-2 in rotation?
				#-> delta between deformation and oscillation
				XA, YA, ZA = self.transform.rotate(angle=-self.rotation_absolute_delta[i][5,2]+self.rotation_absolute_delta[i][npp-2,2], rot_point = self.mbdyn_mesh[i][npp-2,:])
				self.displacement_relative_delta.append((np.array((XA.flatten(),YA.flatten(),ZA.flatten())).T.copy() - self.mbdyn_mesh[i][:npp-2,:]))
				
			self.write_data.clear()
			for i in range(self.patches):
				#self.write_data.append(np.concatenate(np.array((self.displacement[i][:11,:],self.displacement[i][:11,:]))))
				#transform coordinate system (because of the farfield rotation)
				self.transform.importGrid(np.concatenate(np.array((self.displacement_relative_delta[i][:11,:],self.displacement_relative_delta[i][:11,:]))))				
				self.write_data.append(self.transform.rotate(angle=self.rotation_absolute_delta[i][5,2]).T)
				
				#No preCICE
				#self.write_data.append(np.array((XA.flatten()*0,YA.flatten()*0,ZA.flatten()*0)).T)
				
			
			if interface.is_write_data_required(dt):
				for i in range(self.patches):
					interface.write_block_vector_data(self.write_data_id[i], self.vertex_ids[i], self.write_data[i])
			
			print("DUMMY: Advancing in time")
			dt = interface.advance(dt)
			self.current_time_step += decimal.Decimal(str(dt))
			if interface.is_action_required(
				    precice.action_read_iteration_checkpoint()):
				print("DUMMY: Reading iteration checkpoint")
				interface.mark_action_fulfilled(
				    precice.action_read_iteration_checkpoint())
				exit("ERROR MBDyn got no values")
			else:
				#previous displacement = displacement.copy()
				
				#MBDyn advance
				if self.mbdyn.solve(True):
					print("diverged")
					break

			self.iteration += 1
		print("preCICE finalizing")
		interface.finalize()
		print("DUMMY: Closing python solver dummy...")
